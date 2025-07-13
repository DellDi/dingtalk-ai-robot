#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sql_db_agent.py
基于 AutoGen 最新语法实现的数据库查询智能体。
流程：
1. `SQLTranslator` 智能体：将自然语言转换为纯 SQLite SQL 语句；
2. `SQLExecutor` 智能体：调用内部工具执行 SQL，返回原始结果；
3. `SQLFormatter` 智能体：将查询结果格式化成 Markdown 表格；

智能体通过 `RoundRobinGroupChat` 协作，遇到 "TERMINATE" 即结束。
"""
from __future__ import annotations

import sqlite3
from typing import Any, List, Tuple
from loguru import logger

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage

from app.services.ai.client.openai_client import get_openai_client
from app.db_utils import get_conn, DB_PATH

# -----------------------------------------------------------------------------
# SQL 执行工具
# -----------------------------------------------------------------------------


def _execute_sql(sql: str, limit: int = 30) -> Tuple[List[Tuple[Any, ...]], List[str]]:
    """执行 SQL 并返回 (rows, columns)。"""
    conn: sqlite3.Connection = get_conn()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return rows[:limit], columns
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# SQL 查询团队智能体
# -----------------------------------------------------------------------------


class SQLTeamAgent:
    """封装一组 Agent 协作完成 NL -> SQL -> 执行 -> 格式化 全流程。"""

    _instance: "SQLTeamAgent | None" = None  # 单例缓存

    def __new__(cls, *args, **kwargs):  # noqa: D401
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):  # noqa: D401
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.model_client = get_openai_client()
        self._schema_ddl = self._load_db_schema()
        self._build_team()

        logger.info("SQLTeamAgent 初始化完成。")

    # ------------------------- public API -------------------------

    async def process(self, query_text: str) -> str:
        """对外统一调用。"""
        await self.team.reset()
        logger.info(f"SQLTeamAgent 处理查询：{query_text}")
        result_msg = await self.team.run(task=query_text)
        logger.info(f"SQLTeamAgent 处理结果：{result_msg}")
        # result_msg 是 TaskResult
        if not result_msg or not result_msg.messages:
            return "抱歉，未能获取查询结果。"
        # 最后一条消息应含 TERMINATE，倒数第二条即最终内容
        last_content = (
            result_msg.messages[-1].content
            if isinstance(result_msg.messages[-1], TextMessage)
            else ""
        )
        if "TERMINATE" in last_content:
            # 如果执行者返回终止标记作为最后消息
            formatted = last_content.replace("TERMINATE", "").strip()
            return formatted
        # 否则取倒数第二条（Formatter 输出）
        formatter_msg = result_msg.messages[-1]
        if isinstance(formatter_msg, TextMessage):
            return formatter_msg.content.replace("TERMINATE", "").strip()
        return "抱歉，未能正确解析查询结果。"

    # ------------------------- internal ---------------------------

    def _build_team(self) -> None:
        """创建 Translator / Executor / Formatter 三个 Agent."""

        translator = AssistantAgent(
            name="SQLTranslator",
            model_client=self.model_client,
            system_message=(
                "你是一位专业的数据库专家，负责将中文自然语言转换为 SQLite SQL 查询。\n"
                "已知数据库 schema 如下：\n" + self._schema_ddl + "\n"
                "特殊说明：表的列注释的解释说明表是 `columns_comment`。如果检索目的中需要查询表的列注释，可以通过检索columns_comment表中`table_name`和`column_name`对应的记录来获取。\n"
                "请根据用户的问题生成 SQL，仅输出 SQL 语句，不要包裹代码块，不要额外说明。"
            ),
        )

        async def _executor_tool(sql_text: str) -> str:
            """内部工具：执行 SQL 并返回原始行数据。"""
            try:
                rows, columns = _execute_sql(sql_text)
                return str({"columns": columns, "rows": rows})
            except Exception as exc:  # noqa: BLE001
                logger.error("SQL 执行失败: %s", exc, exc_info=True)
                return f"ERROR: {exc}"

        executor = AssistantAgent(
            name="SQLExecutor",
            model_client=self.model_client,
            system_message=(
                "你是 SQL 执行助手。收到上一条消息的纯 SQL 后，调用 `_executor_tool` 工具执行并返回结果 JSON。"
                "然后直接把工具返回内容输出，不做其他解释。"
            ),
            tools=[_executor_tool],
        )

        formatter = AssistantAgent(
            name="SQLFormatter",
            model_client=self.model_client,
            system_message=(
                "你是结果格式化助手。收到上一条消息中的 JSON 数据（包含 columns 和 rows），"
                "将其转换为 Markdown 表格，并在结尾添加 'TERMINATE'。"
            ),
        )

        termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(12)
        self.team = RoundRobinGroupChat(
            participants=[translator, executor, formatter],
            termination_condition=termination,
        )

    def _load_db_schema(self) -> str:
        """动态提取数据库表结构，以便提供给 Translator."""
        conn = sqlite3.connect(DB_PATH)
        try:
            lines: list[str] = []
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            for (tbl,) in tables:
                lines.append(f"表 {tbl} 字段：")
                cols = conn.execute(f"PRAGMA table_info({tbl});").fetchall()
                for _, name, col_type, notnull, _, pk in cols:
                    lines.append(
                        f"- {name} {col_type} {'NOT NULL' if notnull else ''} {'PRIMARY KEY' if pk else ''}"
                    )
            return "\n".join(lines)
        finally:
            conn.close()


def get_sql_team_agent() -> SQLTeamAgent:
    return SQLTeamAgent()

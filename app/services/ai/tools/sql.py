#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sql.py
提供 process_sql_query 供智能体调用。
"""
from __future__ import annotations

from loguru import logger

from app.services.ai.agent.sql_db_agent import get_sql_team_agent

__all__ = ["process_sql_query"]

_sql_team = None

def _get_team():
    global _sql_team  # noqa: PLW0603
    if _sql_team is None:
        _sql_team = get_sql_team_agent()
    return _sql_team


async def process_sql_query(nl_text: str) -> str:  # noqa: D401
    """对外暴露的 SQL 查询工具函数。
    参数：
        nl_text: 要检索查询的原始问题。例如，"当前数据库有哪些用户？"
    """
    logger.info(f"SQLTool 调用，nl_text={nl_text}")
    team = _get_team()
    result = await team.process(nl_text)
    return result

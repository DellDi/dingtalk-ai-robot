#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jira.py
对接 JiraBatchAgent 的批量工单创建功能，供智能体调用。
"""
from __future__ import annotations

from typing import Any, Dict

from loguru import logger

# 延迟导入避免循环依赖

__all__ = ["process_jira_request"]


# 复用单例，避免频繁初始化
_jira_agent = None


def _get_agent():
    global _jira_agent  # noqa: PLW0603
    if _jira_agent is None:
        # 延迟导入避免循环依赖
        from app.services.ai.agent.jira_batch_agent import JiraBatchAgent
        _jira_agent = JiraBatchAgent()
    return _jira_agent


async def process_jira_request(
    request_text: str,
    sender_id: str = "unknown_sender",
    conversation_id: str = "unknown_conversation",
) -> str:
    """处理 Jira 请求并返回文本结果。"""
    logger.info("JiraTool 调用, text=%s", request_text)

    message_payload: Dict[str, Any] = {
        "text": request_text,
        "sender_id": sender_id,
        "conversation_id": conversation_id,
    }
    agent = _get_agent()
    response = await agent.process(message_payload)

    if isinstance(response, dict) and "content" in response:
        return str(response["content"])
    if isinstance(response, str):
        return response

    logger.warning("JiraTool 返回非预期格式: %s", response)
    return "JIRA 任务已提交处理，但响应格式无法直接转换为文本。"

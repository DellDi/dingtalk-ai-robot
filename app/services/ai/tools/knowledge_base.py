#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""knowledge_base.py
封装对 ChromaDBVectorMemory 的检索逻辑，供智能体工具调用。
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from loguru import logger
from autogen_ext.memory.chromadb import ChromaDBVectorMemory

__all__ = ["search_knowledge_base"]


async def _retrieve(vector_memory: ChromaDBVectorMemory, query: str, n_results: int):
    """包装同步的 `retrieve_docs`，在线程池中运行。"""
    return await asyncio.to_thread(
        vector_memory.retrieve_docs,
        query_texts=[query],
        n_results=n_results,
    )


def _format_docs(retrieved_docs_dict) -> str:
    processed: List[str] = []
    if not retrieved_docs_dict or not retrieved_docs_dict.get("documents"):
        return "未在知识库中找到相关信息。"

    docs_for_query = retrieved_docs_dict["documents"][0]
    metadatas = retrieved_docs_dict.get("metadatas", [[]])[0]

    for i, doc in enumerate(docs_for_query):
        source = metadatas[i].get("source", "未知来源") if i < len(metadatas) else "未知来源"
        processed.append(f"来源: {source}\n内容: {doc}")
    return "\n\n---\n\n".join(processed)


async def search_knowledge_base(
    vector_memory: Optional[ChromaDBVectorMemory],
    query: str,
    n_results: int = 3,
) -> str:
    """对共享向量库进行检索并返回格式化结果。"""
    logger.info(f"KnowledgeBaseTool 调用, query={query}")

    if vector_memory is None:
        logger.warning("vector_memory 未配置，无法执行检索")
        return "知识库未正确配置或初始化，无法执行搜索。"

    try:
        docs_dict = await _retrieve(vector_memory, query, n_results)
        return _format_docs(docs_dict)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"KnowledgeBase 检索失败: {exc}")
        return f"知识库检索时发生错误: {exc}"

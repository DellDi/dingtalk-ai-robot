from __future__ import annotations

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.services.knowledge.reranker

使用阿里云 DashScope 文本重排序服务 (gte-rerank-v2) 对检索出的文档进行二次打分并排序。

环境要求：
1. 安装 httpx:  ``pip install httpx``
2. 在环境变量中配置 ``DASHSCOPE_API_KEY``（若未配置，将自动回退到 ``OPENAI_API_KEY``）。

返回值：保留原 ``results`` 结构，新增 ``rerank_score`` 字段，并按该分数降序排列。
"""

from typing import List, Dict, Any, Optional
import os
import httpx
from loguru import logger

DASHSCOPE_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
)


async def _get_api_key() -> Optional[str]:
    """优先从 DASHSCOPE_API_KEY 获取，退回 OPENAI_API_KEY。"""
    return os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")


async def rerank_documents(
    query: str,
    results: List[Dict[str, Any]],
    *,
    model: str = "gte-rerank-v2",
    top_n: int | None = None,
) -> List[Dict[str, Any]]:
    """调用 DashScope 文本重排接口，对 *results* 再打分并返回排序后的列表。

    parameters
    ----------
    query : str
        用户查询文本
    results : List[Dict]
        KnowledgeRetriever.search 返回的结果列表
    model : str, default "gte-rerank-v2"
        DashScope 支持的重排序模型名称
    top_n : int | None
        返回的 top_n；若 None 则维持原列表长度
    """

    api_key = await _get_api_key()
    if not api_key:
        logger.warning("未配置 DASHSCOPE_API_KEY / OPENAI_API_KEY，跳过重排序。")
        return results

    if not results:
        return results

    # DashScope 最多支持 50 篇文档一次重排，超出则截断
    max_docs_supported = 50
    documents = [item["content"] for item in results][:max_docs_supported]

    top_n = top_n if top_n is not None else len(documents)

    payload = {
        "model": model,
        "input": {"query": query, "documents": documents},
        "parameters": {
            "return_documents": False,
            "top_n": top_n,
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            logger.debug("调用 DashScope rerank 接口进行二次排序…")
            resp = await client.post(DASHSCOPE_ENDPOINT, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"DashScope 重排调用失败: {exc}")
        return results

    # 解析返回：{"output": {"results": [{"index":0,"score":0.89}, …]}}
    try:
        rank_items = data["output"]["results"]
    except Exception:
        logger.warning(f"无法解析 DashScope 返回格式: {data}")
        return results

    # Map index -> score
    for item in rank_items:
        idx = item.get("index")
        score = item.get("relevance_score")
        if idx is None or score is None:
            continue
        if idx < len(results):
            results[idx]["rerank_score"] = score

    # 若部分文档未返回分数，置 0
    for res in results:
        res.setdefault("rerank_score", 0.0)

    # 排序
    results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

    # 截断到 top_n
    return results[:top_n] 

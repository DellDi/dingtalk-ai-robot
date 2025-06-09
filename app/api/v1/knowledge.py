#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库API端点模块
"""

from typing import Dict, Any, List, Optional
import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, File, Form, UploadFile # Request, Depends 新增
from pydantic import BaseModel, Field
from loguru import logger

from app.services.knowledge.retriever import KnowledgeRetriever

router = APIRouter()

# 依赖项函数
async def get_knowledge_retriever(request: Request) -> KnowledgeRetriever:
    retriever = request.app.state.knowledge_retriever
    if not retriever or not retriever.initialized:
        # 在这里可以考虑更细致的错误，比如 retriever.initialized 为 False 的情况
        raise HTTPException(status_code=503, detail="知识库服务当前不可用或未初始化。")
    return retriever

class SearchRequest(BaseModel):
    """知识库搜索请求模型"""
    query: str = Field(..., description="搜索查询文本")
    top_k: int = Field(5, description="返回的最大结果数量")


class SearchResponse(BaseModel):
    """知识库搜索响应模型"""
    success: bool
    message: str
    results: Optional[List[Dict[str, Any]]] = None


class DocumentRequest(BaseModel):
    """文档添加请求模型"""
    content: str = Field(..., description="文档内容")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="文档元数据")


class DocumentResponse(BaseModel):
    """文档操作响应模型"""
    success: bool
    message: str
    document_id: Optional[str] = None


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request_data: SearchRequest, # 重命名以避免与 FastAPI Request 冲突
    retriever: KnowledgeRetriever = Depends(get_knowledge_retriever) # 注入依赖
):
    """
    搜索知识库
    """
    try:
        search_results = await retriever.search(
            query_text=request_data.query, 
            k=request_data.top_k
        )
        return SearchResponse(success=True, message="搜索成功", results=search_results)
    except Exception as e:
        logger.error(f"API搜索知识库时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {e}")


@router.post("/add_document", response_model=DocumentResponse)
async def add_document_to_knowledge_base(
    doc_request: DocumentRequest,
    retriever: KnowledgeRetriever = Depends(get_knowledge_retriever) # 注入依赖
):
    """
    添加单个文档到知识库
    """
    try:
        document_to_add = {
            "content": doc_request.content,
            "metadata": doc_request.metadata or {}
        }
        await retriever.add_documents(documents=[document_to_add])
        return DocumentResponse(success=True, message="文档添加成功")
    except Exception as e:
        logger.error(f"API添加文档时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {e}")


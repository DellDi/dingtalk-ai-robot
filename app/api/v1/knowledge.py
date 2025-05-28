#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库API端点模块
"""

from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.services.knowledge.retriever import KnowledgeRetriever

router = APIRouter()


class SearchRequest(BaseModel):
    """知识库搜索请求模型"""
    query: str = Field(..., description="搜索查询文本")
    top_k: int = Field(5, description="返回的最大结果数量")


class SearchResponse(BaseModel):
    """知识库搜索响应模型"""
    success: bool
    message: str
    results: Optional[str] = None


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
async def search_knowledge(request: SearchRequest):
    """
    搜索知识库
    """
    try:
        # 创建知识库检索器实例
        retriever = KnowledgeRetriever()
        
        # 执行搜索
        results = await retriever.search(
            query=request.query,
            top_k=request.top_k
        )
        
        return SearchResponse(
            success=True,
            message="搜索成功",
            results=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索知识库异常: {str(e)}")


@router.post("/documents", response_model=DocumentResponse)
async def add_document(request: DocumentRequest):
    """
    添加文档到知识库
    """
    try:
        # 创建知识库检索器实例
        retriever = KnowledgeRetriever()
        
        # 添加文档
        success = await retriever.add_document(
            content=request.content,
            metadata=request.metadata
        )
        
        if success:
            return DocumentResponse(
                success=True,
                message="文档添加成功",
                document_id="doc_123"  # 模拟ID
            )
        else:
            return DocumentResponse(
                success=False,
                message="文档添加失败"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加文档异常: {str(e)}")


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    metadata: str = Form("{}")
):
    """
    上传文件到知识库
    """
    try:
        # 读取文件内容
        content = await file.read()
        content_text = content.decode("utf-8")
        
        # 创建知识库检索器实例
        retriever = KnowledgeRetriever()
        
        # 添加文档
        success = await retriever.add_document(
            content=content_text,
            metadata={"filename": file.filename}
        )
        
        if success:
            return DocumentResponse(
                success=True,
                message="文件上传成功",
                document_id="doc_456"  # 模拟ID
            )
        else:
            return DocumentResponse(
                success=False,
                message="文件上传失败"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传文件异常: {str(e)}")

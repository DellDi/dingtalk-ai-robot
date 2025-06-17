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

from tempfile import NamedTemporaryFile
from pathlib import Path
from fastapi.concurrency import run_in_threadpool

from app.services.knowledge.retriever import KnowledgeRetriever
from app.services.knowledge.parser import extract_chunks, UnsupportedDocumentError

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
    min_score: float | None = Field(default=0.3, description="相似度阈值 (0-1)，留空则使用后端默认值")


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


class BulkUploadResponse(BaseModel):
    """批量文档上传响应"""
    success: bool
    message: str
    success_count: int = 0
    failed_files: Optional[List[str]] = None


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
            k=request_data.top_k,
            threshold=request_data.min_score,
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


# ------------------------- 新增批量上传接口 ----------------------------- #


@router.post("/upload_document", response_model=BulkUploadResponse)
async def upload_document_to_knowledge_base(
    files: List[UploadFile] = File(..., description="支持 txt / md / pdf / docx"),
    metadata: Optional[str] = Form(None, description="可选的 JSON 字符串元数据"),
    retriever: KnowledgeRetriever = Depends(get_knowledge_retriever),
):
    """上传一个或多个文档并写入知识库。"""

    # 解析公共元数据
    base_meta = {}
    if metadata:
        try:
            base_meta = json.loads(metadata)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"metadata 不是合法 JSON: {e}")

    success_count = 0
    failed: List[str] = []
    all_chunk_docs: List[dict] = []

    for uf in files:
        try:
            # 保存到临时文件，以便解析器直接读取 Path
            suffix = Path(uf.filename).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await uf.read())
                tmp_path = Path(tmp.name)

            # 解析并切片（线程池避免阻塞）
            chunks = await run_in_threadpool(extract_chunks, tmp_path, base_meta)
            all_chunk_docs.extend(chunks)
            success_count += 1
        except UnsupportedDocumentError as ude:
            logger.warning(f"不支持的文档格式 {uf.filename}: {ude}")
            failed.append(uf.filename)
        except Exception as e:
            logger.error(f"解析/嵌入文档 {uf.filename} 时发生错误: {e}")
            failed.append(uf.filename)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)  # cleanup temp file
            except Exception:
                pass
    logger.info(f"成功解析 {all_chunk_docs} 文档，失败 {len(failed)} 个文档")
    if all_chunk_docs:
        try:
            await retriever.add_documents(documents=all_chunk_docs)
        except Exception as e:
            logger.error(f"批量写入向量数据库失败: {e}")
            raise HTTPException(status_code=500, detail=f"写入知识库失败: {e}")

    return BulkUploadResponse(
        success=len(failed) == 0,
        message="上传完成" if not failed else "部分文件上传失败",
        success_count=success_count,
        failed_files=failed or None,
    )

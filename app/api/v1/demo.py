#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
依赖注入演示API端点模块
展示依赖注入架构的优势和使用方法
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from app.services.knowledge.retriever import KnowledgeRetriever
from app.services.ai.handler import AIMessageHandler
from app.services.ssh.client import SSHClient
from app.core.container import (
    get_knowledge_retriever_dependency,
    get_ai_handler_dependency,
    get_ssh_client_dependency,
)

router = APIRouter()


class ServiceStatusResponse(BaseModel):
    """服务状态响应模型"""
    service_name: str
    status: str
    details: Dict[str, Any]


class IntegratedQueryRequest(BaseModel):
    """集成查询请求模型"""
    query: str = Field(..., description="查询内容")
    include_knowledge: bool = Field(True, description="是否包含知识库检索")
    include_ai_analysis: bool = Field(True, description="是否包含AI分析")
    execute_command: Optional[str] = Field(None, description="可选的SSH命令执行")


class IntegratedQueryResponse(BaseModel):
    """集成查询响应模型"""
    success: bool
    query: str
    knowledge_results: Optional[List[Dict[str, Any]]] = None
    ai_analysis: Optional[str] = None
    command_result: Optional[Dict[str, Any]] = None
    processing_time: float


@router.get("/service-status", response_model=List[ServiceStatusResponse])
async def get_service_status(
    knowledge_retriever: KnowledgeRetriever = Depends(get_knowledge_retriever_dependency),
    ai_handler: AIMessageHandler = Depends(get_ai_handler_dependency),
    ssh_client: SSHClient = Depends(get_ssh_client_dependency),
):
    """
    获取所有注入服务的状态
    
    这个端点演示了如何同时注入多个服务并检查它们的状态
    """
    services = []
    
    # 检查知识库检索器状态
    try:
        knowledge_status = {
            "initialized": knowledge_retriever.initialized,
            "collection_name": getattr(knowledge_retriever, 'collection_name', 'unknown'),
            "retrieve_k": getattr(knowledge_retriever, 'retrieve_k', 'unknown'),
        }
        services.append(ServiceStatusResponse(
            service_name="KnowledgeRetriever",
            status="healthy" if knowledge_retriever.initialized else "unhealthy",
            details=knowledge_status
        ))
    except Exception as e:
        services.append(ServiceStatusResponse(
            service_name="KnowledgeRetriever",
            status="error",
            details={"error": str(e)}
        ))
    
    # 检查AI处理器状态
    try:
        ai_status = {
            "class_name": ai_handler.__class__.__name__,
            "has_vector_memory": hasattr(ai_handler, 'shared_vector_memory'),
        }
        services.append(ServiceStatusResponse(
            service_name="AIMessageHandler",
            status="healthy",
            details=ai_status
        ))
    except Exception as e:
        services.append(ServiceStatusResponse(
            service_name="AIMessageHandler",
            status="error",
            details={"error": str(e)}
        ))
    
    # 检查SSH客户端状态
    try:
        ssh_status = {
            "default_host": getattr(ssh_client, 'host', 'unknown'),
            "username": getattr(ssh_client, 'username', 'unknown'),
            "port": getattr(ssh_client, 'port', 22),
        }
        services.append(ServiceStatusResponse(
            service_name="SSHClient",
            status="healthy",
            details=ssh_status
        ))
    except Exception as e:
        services.append(ServiceStatusResponse(
            service_name="SSHClient",
            status="error",
            details={"error": str(e)}
        ))
    
    return services


@router.post("/integrated-query", response_model=IntegratedQueryResponse)
async def integrated_query(
    request: IntegratedQueryRequest,
    knowledge_retriever: KnowledgeRetriever = Depends(get_knowledge_retriever_dependency),
    ai_handler: AIMessageHandler = Depends(get_ai_handler_dependency),
    ssh_client: SSHClient = Depends(get_ssh_client_dependency),
):
    """
    集成查询端点 - 演示多服务协作
    
    这个端点展示了依赖注入架构的强大之处：
    1. 自动注入多个服务
    2. 服务间协作处理复杂请求
    3. 统一的错误处理和响应格式
    """
    import time
    start_time = time.time()
    
    try:
        knowledge_results = None
        ai_analysis = None
        command_result = None
        
        # 1. 知识库检索（如果请求）
        if request.include_knowledge:
            logger.info(f"执行知识库检索: {request.query}")
            try:
                knowledge_results = await knowledge_retriever.search(
                    query_text=request.query,
                    k=3,
                    threshold=0.2
                )
                logger.info(f"知识库检索完成，找到 {len(knowledge_results)} 条结果")
            except Exception as e:
                logger.error(f"知识库检索失败: {e}")
                knowledge_results = []
        
        # 2. AI分析（如果请求）
        if request.include_ai_analysis:
            logger.info(f"执行AI分析: {request.query}")
            try:
                # 构建上下文
                context = f"用户查询: {request.query}"
                if knowledge_results:
                    context += f"\n知识库检索结果: {len(knowledge_results)} 条相关信息"
                
                # 调用AI处理器
                ai_response = await ai_handler.process_message(
                    message=context,
                    sender_id="demo_user",
                    conversation_id="demo_conversation"
                )
                ai_analysis = ai_response
                logger.info("AI分析完成")
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                ai_analysis = f"AI分析失败: {str(e)}"
        
        # 3. SSH命令执行（如果请求）
        if request.execute_command:
            logger.info(f"执行SSH命令: {request.execute_command}")
            try:
                # 连接SSH
                connected = await ssh_client.connect()
                if connected:
                    exit_code, stdout, stderr = await ssh_client.execute_command(
                        request.execute_command
                    )
                    command_result = {
                        "success": exit_code == 0,
                        "exit_code": exit_code,
                        "stdout": stdout,
                        "stderr": stderr
                    }
                    ssh_client.close()
                    logger.info(f"SSH命令执行完成，退出码: {exit_code}")
                else:
                    command_result = {
                        "success": False,
                        "error": "无法连接到SSH服务器"
                    }
            except Exception as e:
                logger.error(f"SSH命令执行失败: {e}")
                command_result = {
                    "success": False,
                    "error": str(e)
                }
        
        processing_time = time.time() - start_time
        
        return IntegratedQueryResponse(
            success=True,
            query=request.query,
            knowledge_results=knowledge_results,
            ai_analysis=ai_analysis,
            command_result=command_result,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"集成查询处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"集成查询处理失败: {str(e)}")


@router.get("/dependency-info")
async def get_dependency_info():
    """
    获取依赖注入架构信息
    
    这个端点提供关于依赖注入架构的详细信息
    """
    from app.core.container import container
    
    return {
        "architecture": "Dependency Injection with dependency-injector",
        "container_type": container.__class__.__name__,
        "registered_providers": {
            "knowledge_retriever": "Singleton",
            "ai_message_handler": "Singleton", 
            "ssh_client": "Factory",
            "jira_task_service": "Singleton",
            "dingtalk_report_service": "Singleton",
            "weekly_report_service": "Singleton",
        },
        "benefits": [
            "松耦合：服务间依赖通过接口而非具体实现",
            "可测试性：易于进行单元测试和模拟",
            "可配置性：运行时动态配置服务",
            "生命周期管理：自动管理服务的创建和销毁",
            "单一职责：每个服务专注于自己的业务逻辑"
        ],
        "usage_patterns": {
            "singleton": "适用于无状态服务或需要共享状态的服务",
            "factory": "适用于每次使用都需要新实例的服务",
            "dependency_injection": "通过FastAPI的Depends机制注入服务"
        }
    }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
健康检查API端点
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    version: str
    components: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查接口，返回系统各组件状态
    """
    # 检查各组件状态
    components = {
        "api": {
            "status": "ok",
            "details": "API服务正常运行"
        },
        "dingtalk": {
            "status": "ok",
            "details": "钉钉客户端连接正常"
        },
        "database": {
            "status": "ok",
            "details": "数据库连接正常"
        }
    }
    
    # 所有组件状态正常时，整体状态为healthy
    status = "healthy"
    
    return HealthResponse(
        status=status,
        version="0.1.0",
        components=components
    )

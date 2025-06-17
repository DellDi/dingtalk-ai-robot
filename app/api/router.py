#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API路由模块
"""

from fastapi import APIRouter

from app.api.v1 import dingtalk, health, jira, knowledge, logs, ssh

# 创建主路由器
api_router = APIRouter()

# 注册子路由
api_router.include_router(health.router, tags=["健康检查"])
api_router.include_router(dingtalk.router, prefix="/dingtalk", tags=["钉钉"])
api_router.include_router(jira.router, prefix="/jira", tags=["JIRA"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(logs.router, prefix="/logs", tags=["日志管理"])
api_router.include_router(ssh.router, prefix="/ssh", tags=["服务器管理"])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉AI机器人主程序入口
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.core.dingtalk_client import DingTalkClient
from app.core.scheduler import start_scheduler

# 加载环境变量
load_dotenv()

# 创建线程池
thread_pool = ThreadPoolExecutor(max_workers=5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时执行
    logger.info("🚀 启动钉钉机器人服务")
    
    # 启动钉钉客户端（在单独线程中运行）
    dingtalk_client = DingTalkClient()
    loop = asyncio.get_event_loop()
    dingtalk_future = loop.run_in_executor(thread_pool, dingtalk_client.start_forever)
    
    # 启动定时任务
    scheduler_task = asyncio.create_task(start_scheduler())
    
    yield
    
    # 关闭时执行
    logger.info("🔄 关闭钉钉机器人服务")
    dingtalk_client.stop()
    scheduler_task.cancel()
    thread_pool.shutdown(wait=False)


# 创建FastAPI应用
app = FastAPI(
    title="钉钉AI机器人",
    description="集成AI问答、知识库检索、JIRA管理和服务器维护功能的钉钉机器人",
    version="0.1.0",
    lifespan=lifespan,
)

# 导入路由
from app.api.router import api_router
app.include_router(api_router)


@app.get("/")
async def root():
    """
    健康检查接口
    """
    return {"status": "ok", "message": "钉钉AI机器人服务运行中"}


if __name__ == "__main__":
    """
    直接运行此文件时执行的入口
    """
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )

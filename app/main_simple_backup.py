#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉AI机器人主程序入口 - 简化版本，修复热重载问题
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from app.core.config import settings
from app.core.dingtalk_client import DingTalkClient
from app.core.logger import setup_logging
from app.core.scheduler import start_scheduler
from app.services.knowledge.retriever import KnowledgeRetriever

# 加载环境变量
load_dotenv()

# 初始化日志系统
setup_logging()

# 创建线程池（Windows 优化）
import platform
import signal

# 检测操作系统
is_windows = platform.system() == "Windows"

if is_windows:
    # Windows 下使用更小的线程池，便于管理
    thread_pool = ThreadPoolExecutor(max_workers=2)
else:
    # Mac/Linux 使用标准配置
    thread_pool = ThreadPoolExecutor(max_workers=5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理 - 简化版本，基于历史版本
    """
    # 启动时执行
    from loguru import logger
    logger.info("🚀 启动钉钉机器人服务")

    # 简化启动逻辑，回归老版本的简单方式

    # 初始化知识库检索器
    logger.info("🧠 初始化知识库检索器...")
    knowledge_retriever = KnowledgeRetriever(
        collection_name=settings.CHROMA_DEFAULT_COLLECTION_NAME,
        persistence_path=settings.VECTOR_DB_PATH,
        retrieve_k=settings.CHROMA_DEFAULT_K,
        retrieve_score_threshold=settings.CHROMA_DEFAULT_SCORE_THRESHOLD,
    )
    await knowledge_retriever.initialize()

    if knowledge_retriever.initialized:
        app.state.knowledge_retriever = knowledge_retriever
        logger.info("✅ 知识库检索器初始化成功并已共享")
    else:
        app.state.knowledge_retriever = None
        logger.error("❌ 知识库检索器初始化失败！")

    # 启动钉钉客户端（回归老版本的简单方式）
    dingtalk_client = DingTalkClient(knowledge_retriever=app.state.knowledge_retriever)
    loop = asyncio.get_event_loop()
    # 正确调用钉钉客户端的start_forever方法（完全按照老版本）
    dingtalk_future = loop.run_in_executor(thread_pool, dingtalk_client.stream_client.start_forever)

    # 启动定时任务
    logger.info("⏰ 启动定时任务")
    scheduler_task = asyncio.create_task(start_scheduler())

    logger.info("✅ 所有服务启动完成")
    logger.info(f"🖥️ 运行平台: {platform.system()} - Windows优化: {is_windows}")






    yield

    # 关闭时执行（简化版本，基于历史版本）
    logger.info("🔄 关闭钉钉机器人服务")

    # 关闭知识库检索器
    if hasattr(app.state, 'knowledge_retriever') and app.state.knowledge_retriever:
        logger.info("🚪 关闭知识库检索器...")
        app.state.knowledge_retriever.close()

    # 关闭钉钉客户端（Windows 优化）
    try:
        # 首先取消future任务
        if dingtalk_future and not dingtalk_future.done():
            dingtalk_future.cancel()

        # 然后停止客户端
        dingtalk_client.stop()

        # 停止定时任务
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task

        # Windows 特定的线程池关闭
        if is_windows:
            # Windows 下使用更激进的关闭方式
            import os
            import threading
            import sys

            # 强制关闭线程池，不等待任何任务
            thread_pool.shutdown(wait=False)

            # 给一点时间让线程自然结束
            await asyncio.sleep(0.1)

            # 检查活跃线程
            active_threads = threading.active_count()
            if active_threads > 1:
                logger.warning(f"Windows: 仍有 {active_threads} 个活跃线程，强制退出进程")
                # 在 Windows 下，如果线程无法正常关闭，强制退出
                # 这样 uvicorn 可以重启新进程
                os._exit(0)
        else:
            # Mac/Linux 使用标准方式
            thread_pool.shutdown(wait=False)

    except Exception as e:
        logger.warning(f"关闭服务时出现异常: {e}")
        # 即使出现异常，也要强制关闭线程池
        thread_pool.shutdown(wait=False)


# 创建FastAPI应用
app = FastAPI(
    title="钉钉AI机器人",
    description="集成AI问答、知识库检索、JIRA管理和服务器维护功能的钉钉机器人",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",       # Swagger UI 文档
    redoc_url="/redoc",     # ReDoc 文档
    openapi_url="/openapi.json",
)



# 设置中间件
from app.core.middleware import setup_middleware
setup_middleware(app)

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

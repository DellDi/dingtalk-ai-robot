#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉AI机器人主程序入口
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
from app.core.container import container, initialize_container, cleanup_container
from app.core.middleware import setup_middleware

# 加载环境变量
load_dotenv()

# 初始化日志系统
setup_logging()

# 创建线程池
thread_pool = ThreadPoolExecutor(max_workers=5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理 - 使用依赖注入容器
    优化热重载稳定性
    """
    # 启动时执行
    from loguru import logger
    logger.info("🚀 启动钉钉机器人服务")

    dingtalk_client = None
    scheduler_task = None
    dingtalk_future = None

    try:
        # 初始化依赖注入容器
        success = await initialize_container()
        if not success:
            logger.error("❌ 依赖注入容器初始化失败，服务启动中止")
            raise RuntimeError("依赖注入容器初始化失败")

        # 获取知识库检索器实例
        knowledge_retriever = container.knowledge_retriever()

        # 启动钉钉客户端 - 使用改进的方式支持热重载
        logger.info("🔗 启动钉钉客户端")
        dingtalk_client = DingTalkClient(knowledge_retriever=knowledge_retriever)

        # 检查是否为开发环境（通过uvicorn的reload参数判断）
        import sys
        is_reload_mode = '--reload' in sys.argv or any('reload' in arg for arg in sys.argv)

        if is_reload_mode:
            logger.info("🔧 检测到热重载模式，钉钉客户端将在独立进程中运行")
            # 在热重载模式下，不启动钉钉客户端，避免阻塞
            dingtalk_future = None
        else:
            logger.info("🚀 生产模式，启动钉钉客户端")
            loop = asyncio.get_event_loop()
            dingtalk_future = loop.run_in_executor(thread_pool, dingtalk_client.stream_client.start_forever)

        # 启动定时任务
        logger.info("⏰ 启动定时任务")
        scheduler_task = asyncio.create_task(start_scheduler())

        logger.info("✅ 所有服务启动完成")
        if is_reload_mode:
            logger.info("🔧 热重载模式：钉钉客户端已跳过，API功能正常可用")
        else:
            logger.info("🚀 生产模式：所有功能已启动")

        yield

    except Exception as e:
        logger.error(f"❌ 应用启动失败: {e}")
        raise
    finally:
        # 关闭时执行 - 确保所有资源都被正确清理
        logger.info("🔄 开始关闭钉钉机器人服务")

        # 1. 首先停止定时任务

        if scheduler_task and not scheduler_task.done():
            logger.info("🛑 停止定时任务...")
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task
            logger.info("✅ 定时任务已停止")

        # 2. 停止钉钉客户端 - 使用更温和的方式
        if dingtalk_client:
            logger.info("🛑 停止钉钉客户端...")
            try:
                # 首先取消future任务
                if dingtalk_future and not dingtalk_future.done():
                    logger.info("取消钉钉客户端future任务...")
                    dingtalk_future.cancel()

                # 然后停止客户端
                dingtalk_client.stop()

                # 给一点时间让连接正常关闭
                await asyncio.sleep(0.1)

                logger.info("✅ 钉钉客户端已停止")
            except Exception as e:
                logger.warning(f"⚠️ 钉钉客户端停止时出现异常: {e}")
                # 即使出现异常也继续清理流程

        # 3. 清理依赖注入容器
        logger.info("🧹 清理依赖注入容器...")
        try:
            await cleanup_container()
            logger.info("✅ 依赖注入容器清理完成")
        except Exception as e:
            logger.warning(f"⚠️ 容器清理时出现异常: {e}")

        # 4. 关闭线程池 - 使用非阻塞方式
        logger.info("🛑 关闭线程池...")
        try:
            # 使用非阻塞方式关闭，避免热重载时卡住
            thread_pool.shutdown(wait=False)
            logger.info("✅ 线程池关闭请求已发送")
        except Exception as e:
            logger.warning(f"⚠️ 线程池关闭时出现异常: {e}")

        # 5. 短暂等待，让资源有时间释放
        await asyncio.sleep(0.2)

        logger.info("🎉 钉钉机器人服务关闭完成")


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

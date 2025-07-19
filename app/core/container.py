#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
依赖注入容器模块
使用dependency-injector实现IoC容器，管理应用中的所有服务依赖
"""

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject
from typing import Optional

from app.core.config import settings
from app.services.knowledge.retriever import KnowledgeRetriever
from app.services.ai.handler import AIMessageHandler
from app.services.ssh.client import SSHClient
from app.services.jira.tasks import JiraTaskService
from app.services.dingtalk.report_service import DingTalkReportService
from app.services.weekly_report_service import WeeklyReportService


class ApplicationContainer(containers.DeclarativeContainer):
    """应用依赖注入容器"""

    # 配置提供者
    config = providers.Configuration()

    # 知识库检索器 - 单例模式
    knowledge_retriever = providers.Singleton(
        KnowledgeRetriever,
        collection_name=settings.CHROMA_DEFAULT_COLLECTION_NAME,
        persistence_path=settings.VECTOR_DB_PATH,
        retrieve_k=settings.CHROMA_DEFAULT_K,
        retrieve_score_threshold=settings.CHROMA_DEFAULT_SCORE_THRESHOLD,
    )

    # AI消息处理器 - 单例模式（延迟初始化）
    ai_message_handler = providers.Singleton(
        AIMessageHandler,
        vector_memory=None,  # 将在初始化时动态设置
    )

    # SSH客户端 - 工厂模式（每次调用创建新实例）
    ssh_client = providers.Factory(
        SSHClient,
        host=settings.SSH_DEFAULT_HOST or "localhost",
        username=settings.SSH_USERNAME,
        key_path=settings.SSH_KEY_PATH,
        password=settings.SSH_PASSWORD,
    )

    # JIRA任务服务 - 单例模式
    jira_task_service = providers.Singleton(
        JiraTaskService,
        jira_url=settings.JIRA_URL,
        username=settings.JIRA_USERNAME,
        api_token=settings.JIRA_API_TOKEN,
        project_key=settings.JIRA_PROJECT_KEY,
    )

    # 钉钉报告服务 - 单例模式
    dingtalk_report_service = providers.Singleton(
        DingTalkReportService,
        client_id=settings.DINGTALK_CLIENT_ID,
        client_secret=settings.DINGTALK_CLIENT_SECRET,
    )

    # 周报服务 - 单例模式（不传递ai_handler，让它使用默认的weekly_report_agent）
    weekly_report_service = providers.Singleton(
        WeeklyReportService,
        dingtalk_report_service=dingtalk_report_service,
        ai_handler=None,  # 使用默认的weekly_report_agent
    )


# 全局容器实例
container = ApplicationContainer()


# 依赖注入装饰器和辅助函数
def get_knowledge_retriever() -> KnowledgeRetriever:
    """获取知识库检索器实例"""
    return container.knowledge_retriever()


def get_ai_message_handler() -> AIMessageHandler:
    """获取AI消息处理器实例"""
    return container.ai_message_handler()


def get_ssh_client() -> SSHClient:
    """获取SSH客户端实例（工厂模式）"""
    return container.ssh_client()


def get_jira_task_service() -> JiraTaskService:
    """获取JIRA任务服务实例"""
    return container.jira_task_service()


def get_dingtalk_report_service() -> DingTalkReportService:
    """获取钉钉报告服务实例"""
    return container.dingtalk_report_service()


def get_weekly_report_service() -> WeeklyReportService:
    """获取周报服务实例"""
    return container.weekly_report_service()


# 异步初始化函数
async def initialize_container():
    """初始化容器中的异步服务"""
    from loguru import logger

    logger.info("🔧 开始初始化依赖注入容器...")

    try:
        # 初始化知识库检索器
        logger.info("📚 初始化知识库检索器...")
        knowledge_retriever = container.knowledge_retriever()
        await knowledge_retriever.initialize()

        if not knowledge_retriever.initialized:
            logger.error("❌ 知识库检索器初始化失败")
            return False

        logger.info("✅ 知识库检索器初始化成功")

        # 获取向量内存并重新配置AI消息处理器
        logger.info("🤖 配置AI消息处理器的向量内存...")
        vector_memory = getattr(knowledge_retriever, 'vector_memory', None)

        if vector_memory:
            # 重新配置AI处理器提供者，传入向量内存
            container.ai_message_handler.override(
                providers.Singleton(
                    AIMessageHandler,
                    vector_memory=vector_memory
                )
            )
            logger.info("✅ AI消息处理器向量内存配置成功")
        else:
            logger.warning("⚠️ 无法获取向量内存，AI消息处理器将以有限功能运行")

        # 初始化AI消息处理器
        logger.info("🤖 初始化AI消息处理器...")
        ai_handler = container.ai_message_handler()
        logger.info("✅ AI消息处理器初始化成功")

        # 初始化其他需要异步初始化的服务
        # ...

        logger.info("🎉 依赖注入容器初始化完成")
        return True

    except Exception as e:
        logger.error(f"❌ 依赖注入容器初始化失败: {e}", exc_info=True)
        return False


async def cleanup_container():
    """清理容器中的资源"""
    from loguru import logger

    logger.info("🧹 开始清理依赖注入容器...")

    try:
        # 清理知识库检索器
        knowledge_retriever = container.knowledge_retriever()
        if hasattr(knowledge_retriever, 'close'):
            knowledge_retriever.close()
            logger.info("✅ 知识库检索器已清理")

        # 重置AI处理器的覆盖
        container.ai_message_handler.reset_override()
        logger.info("✅ AI消息处理器覆盖已重置")

        # 清理其他需要清理的服务
        # ...

        logger.info("🎉 依赖注入容器清理完成")

    except Exception as e:
        logger.error(f"❌ 依赖注入容器清理失败: {e}", exc_info=True)


# 用于FastAPI依赖注入的函数
async def get_knowledge_retriever_dependency() -> KnowledgeRetriever:
    """FastAPI依赖注入：获取知识库检索器"""
    retriever = get_knowledge_retriever()
    if not retriever.initialized:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="知识库服务当前不可用")
    return retriever


async def get_ai_handler_dependency() -> AIMessageHandler:
    """FastAPI依赖注入：获取AI消息处理器"""
    return get_ai_message_handler()


async def get_ssh_client_dependency() -> SSHClient:
    """FastAPI依赖注入：获取SSH客户端"""
    return get_ssh_client()


async def get_jira_service_dependency() -> JiraTaskService:
    """FastAPI依赖注入：获取JIRA任务服务"""
    return get_jira_task_service()


async def get_weekly_report_service_dependency() -> WeeklyReportService:
    """FastAPI依赖注入：获取周报服务"""
    return get_weekly_report_service()

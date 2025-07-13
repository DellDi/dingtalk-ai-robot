#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试Gemini模型客户端集成
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from app.services.ai.client.openai_client import get_gemini_client
from app.services.ai.weekly_report_agent import WeeklyReportAgent


async def test_gemini_client():
    """测试Gemini客户端基本功能"""
    logger.info("🧪 开始测试Gemini客户端...")

    try:
        # 检查环境变量
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            logger.warning("⚠️ 未配置GEMINI_API_KEY环境变量，将使用默认OpenAI客户端")
        else:
            logger.info("✅ 检测到GEMINI_API_KEY配置")

        # 创建Gemini客户端
        gemini_client = get_gemini_client()
        logger.info(f"✅ Gemini客户端创建成功: {type(gemini_client)}")

        # 简单测试
        from autogen_core.models import UserMessage
        test_message = UserMessage(content="请用中文回答：什么是人工智能？", source="user")

        logger.info("🔄 发送测试消息到Gemini...")
        response = await gemini_client.create([test_message])
        logger.info(f"✅ Gemini响应成功: {response.content[:100]}...")

        await gemini_client.close()
        return True

    except Exception as e:
        logger.error(f"❌ Gemini客户端测试失败: {e}")
        return False


async def test_weekly_report_with_gemini():
    """测试周报智能体的Gemini集成"""
    logger.info("🧪 开始测试周报智能体Gemini集成...")

    try:
        # 创建周报智能体
        agent = WeeklyReportAgent()
        logger.info("✅ 周报智能体创建成功")

        # 检查智能体配置
        logger.info(f"📊 Summarizer智能体创建成功: {agent.summarizer_agent.name}")
        logger.info(f"📊 Reviewer智能体创建成功: {agent.reviewer_agent.name}")
        logger.info(f"📊 模型客户端配置: OpenAI={type(agent.model_client)}, Gemini={type(agent.gemini_model_client)}")

        # 测试数据
        test_logs = [
            {
                "user_id": "test_user",
                "content": "完成了用户认证模块的开发，包括登录、注册和密码重置功能",
                "created_at": "2024-01-15 09:00:00"
            },
            {
                "user_id": "test_user",
                "content": "修复了数据库连接池的内存泄漏问题，优化了查询性能",
                "created_at": "2024-01-16 14:30:00"
            },
            {
                "user_id": "test_user",
                "content": "参与了技术架构评审会议，讨论了微服务拆分方案",
                "created_at": "2024-01-17 16:00:00"
            }
        ]

        logger.info("🔄 生成周报总结...")
        summary = await agent.generate_weekly_summary(test_logs)

        if summary:
            logger.info("✅ 周报生成成功!")
            logger.info(f"📄 周报内容预览:\n{summary[:200]}...")
            return True
        else:
            logger.error("❌ 周报生成失败")
            return False

    except Exception as e:
        logger.error(f"❌ 周报智能体测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    logger.info("🚀 开始Gemini集成测试")

    # 测试1: Gemini客户端基本功能
    gemini_test_result = await test_gemini_client()

    # 测试2: 周报智能体集成
    weekly_report_test_result = await test_weekly_report_with_gemini()

    # 总结测试结果
    logger.info("📊 测试结果总结:")
    logger.info(f"  - Gemini客户端测试: {'✅ 通过' if gemini_test_result else '❌ 失败'}")
    logger.info(f"  - 周报智能体测试: {'✅ 通过' if weekly_report_test_result else '❌ 失败'}")

    if gemini_test_result and weekly_report_test_result:
        logger.info("🎉 所有测试通过！Gemini集成成功")
    else:
        logger.warning("⚠️ 部分测试失败，请检查配置和网络连接")


if __name__ == "__main__":
    asyncio.run(main())

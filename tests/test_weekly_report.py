#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周报功能测试脚本
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.weekly_report_service import weekly_report_service
from app.db_utils import get_first_user_id
from loguru import logger


async def test_check_logs():
    """测试检查用户日志功能"""
    logger.info("🔍 测试检查用户日志功能")
    result = await weekly_report_service.check_user_weekly_logs()
    
    if result["success"]:
        logger.info("✅ 日志检查成功")
        logger.info(f"📊 日志数量: {result['data']['logs_count']}")
        logger.info(f"📝 整合内容预览: {result['data']['combined_content'][:200]}...")
    else:
        logger.error(f"❌ 日志检查失败: {result['message']}")
    
    return result


async def test_generate_summary(content: str):
    """测试生成周报总结功能"""
    logger.info("🤖 测试生成周报总结功能")
    result = await weekly_report_service.generate_weekly_summary(content, use_quick_mode=True)
    
    if result["success"]:
        logger.info("✅ 周报总结生成成功")
        logger.info(f"📄 总结内容: {result['data']['summary_content']}")
    else:
        logger.error(f"❌ 周报总结生成失败: {result['message']}")
    
    return result


async def test_full_workflow():
    """测试完整的周报工作流程"""
    logger.info("🚀 开始测试完整的周报工作流程")
    
    try:
        # 1. 检查日志
        log_result = await test_check_logs()
        if not log_result["success"]:
            return
        
        # 2. 生成总结
        content = log_result["data"]["combined_content"]
        summary_result = await test_generate_summary(content)
        if not summary_result["success"]:
            return
        
        # 3. 测试自动任务（不实际发送到钉钉）
        logger.info("🔄 测试自动周报任务")
        auto_result = await weekly_report_service.auto_weekly_report_task()
        
        if auto_result["success"]:
            logger.info("✅ 自动周报任务测试成功")
            logger.info("📊 任务执行结果:")
            logger.info(f"  - 日志数量: {auto_result['data']['logs_info']['logs_count']}")
            logger.info(f"  - AI模式: {auto_result['data']['summary_info']['mode']}")
            logger.info(f"  - 报告ID: {auto_result['data']['send_info']['report_id']}")
        else:
            logger.error(f"❌ 自动周报任务测试失败: {auto_result['message']}")
        
        logger.info("🎉 周报功能测试完成")
        
    except Exception as e:
        logger.error(f"💥 测试过程中发生异常: {e}")


async def test_database():
    """测试数据库连接和基本功能"""
    logger.info("🗄️ 测试数据库连接")
    
    try:
        from app.db_utils import get_conn
        conn = get_conn()
        
        # 测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        logger.info(f"✅ 数据库连接成功，发现 {len(tables)} 个表")
        for table in tables:
            logger.info(f"  - {table[0]}")
        
        # 检查用户
        user_id = get_first_user_id()
        if user_id:
            logger.info(f"👤 找到用户ID: {user_id}")
        else:
            logger.warning("⚠️ 未找到用户数据")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ 数据库测试失败: {e}")


async def main():
    """主测试函数"""
    logger.info("🧪 开始周报功能测试")
    
    # 测试数据库
    await test_database()
    
    print("\n" + "="*50)
    
    # 测试完整工作流程
    await test_full_workflow()
    
    logger.info("🏁 所有测试完成")


if __name__ == "__main__":
    asyncio.run(main())

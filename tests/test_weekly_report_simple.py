#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周报功能简化测试脚本（跳过钉钉API调用）
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.weekly_report_service import weekly_report_service
from loguru import logger


async def test_core_functionality():
    """测试核心功能（不包含钉钉API调用）"""
    logger.info("🧪 开始测试周报核心功能")
    
    try:
        # 1. 测试日志检查
        logger.info("📋 1. 测试日志检查功能")
        log_result = await weekly_report_service.check_user_weekly_logs()
        
        if log_result["success"]:
            logger.info("✅ 日志检查成功")
            logger.info(f"📊 找到 {log_result['data']['logs_count']} 条日志")
            
            # 2. 测试AI总结生成（快速模式）
            logger.info("🤖 2. 测试AI总结生成（快速模式）")
            content = log_result["data"]["combined_content"]
            
            summary_result = await weekly_report_service.generate_weekly_summary(
                content, use_quick_mode=True
            )
            
            if summary_result["success"]:
                logger.info("✅ 快速模式总结生成成功")
                logger.info("📄 生成的周报总结:")
                print("\n" + "="*60)
                print(summary_result["data"]["summary_content"])
                print("="*60 + "\n")
                
                # 3. 测试AI总结生成（标准模式）
                logger.info("🎯 3. 测试AI总结生成（标准模式）")
                
                standard_result = await weekly_report_service.generate_weekly_summary(
                    content, use_quick_mode=False
                )
                
                if standard_result["success"]:
                    logger.info("✅ 标准模式总结生成成功")
                    logger.info("📄 标准模式生成的周报总结:")
                    print("\n" + "="*60)
                    print(standard_result["data"]["summary_content"])
                    print("="*60 + "\n")
                else:
                    logger.warning(f"⚠️ 标准模式总结生成失败: {standard_result['message']}")
                
            else:
                logger.error(f"❌ 快速模式总结生成失败: {summary_result['message']}")
                
        else:
            logger.error(f"❌ 日志检查失败: {log_result['message']}")
            
    except Exception as e:
        logger.error(f"💥 测试过程中发生异常: {e}")


async def test_date_functions():
    """测试日期相关功能"""
    logger.info("📅 测试日期相关功能")
    
    try:
        # 测试获取当前周日期
        current_week = weekly_report_service.get_current_week_dates()
        logger.info(f"📆 当前周: {current_week[0]} 到 {current_week[1]}")
        
        # 测试获取上周日期
        last_week = weekly_report_service.get_week_dates_by_offset(-1)
        logger.info(f"📆 上周: {last_week[0]} 到 {last_week[1]}")
        
        # 测试获取下周日期
        next_week = weekly_report_service.get_week_dates_by_offset(1)
        logger.info(f"📆 下周: {next_week[0]} 到 {next_week[1]}")
        
        logger.info("✅ 日期功能测试通过")
        
    except Exception as e:
        logger.error(f"❌ 日期功能测试失败: {e}")


async def main():
    """主测试函数"""
    logger.info("🚀 开始周报功能简化测试")
    
    # 测试日期功能
    await test_date_functions()
    
    print("\n" + "="*50)
    
    # 测试核心功能
    await test_core_functionality()
    
    logger.info("🎉 所有测试完成")


if __name__ == "__main__":
    asyncio.run(main())

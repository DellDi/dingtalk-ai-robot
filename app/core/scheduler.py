#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
定时任务调度器模块
"""

import asyncio
from datetime import datetime

import schedule
from loguru import logger

from app.core.logger import cleanup_logs
from app.services.jira.tasks import check_jira_tasks_compliance


async def start_scheduler():
    """
    启动定时任务调度器
    """
    logger.info("启动定时任务调度器")

    # 配置定时任务
    # 工作日每天上午10点和下午4点检查JIRA任务
    schedule.every().monday.at("10:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().monday.at("16:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().tuesday.at("10:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().tuesday.at("16:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().wednesday.at("10:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().wednesday.at("16:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().thursday.at("10:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().thursday.at("16:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().friday.at("10:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))
    schedule.every().friday.at("16:00").do(lambda: asyncio.create_task(check_jira_tasks_compliance()))

    # 每天凌晨2点清理过期日志文件
    schedule.every().day.at("02:00").do(lambda: asyncio.create_task(cleanup_logs_task()))

    # 运行调度器
    try:
        while True:
            schedule.run_pending()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.debug(f"定时任务调度器运行中... {now}")
            await asyncio.sleep(3600)  # 每小时检查一次
    except asyncio.CancelledError:
        logger.info("定时任务调度器已停止")
    except Exception as e:
        logger.error(f"定时任务调度器异常: {e}")
        raise


async def cleanup_logs_task():
    """
    日志清理任务
    """
    try:
        logger.info("🧹 开始执行定时日志清理任务...")
        cleanup_logs()
        logger.info("✅ 定时日志清理任务完成")
    except Exception as e:
        logger.error(f"❌ 定时日志清理任务失败: {e}")

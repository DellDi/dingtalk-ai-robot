#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
定时任务调度器模块
"""

import asyncio
import schedule
from datetime import datetime
from loguru import logger

from app.core.logger import cleanup_logs
from app.services.jira.tasks import check_jira_tasks_compliance
from app.services.weekly_report_service import weekly_report_service
from app.services.conversation_log_service import cleanup_conversation_logs


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

    # 每周一凌晨3点清理7天前的对话记录
    schedule.every().monday.at("03:00").do(lambda: asyncio.create_task(cleanup_conversation_logs_task(days=7)))

    # 每周六20:30执行周报生成任务
    schedule.every().saturday.at("20:30").do(lambda: asyncio.create_task(weekly_report_task()))

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
        logger.info("开始执行日志清理任务")
        await cleanup_logs()
        logger.info("日志清理任务完成")
    except Exception as e:
        logger.error(f"日志清理任务失败: {e}")

async def cleanup_conversation_logs_task(days: int = 30):
    """
    记录对话记录清理任务
    """
    try:
        logger.info("开始执行记录对话记录清理任务")
        await cleanup_conversation_logs(days)
        logger.info("记录对话记录清理任务完成")
    except Exception as e:
        logger.error(f"记录对话记录清理任务失败: {e}")


async def weekly_report_task():
    """
    周报生成任务
    每周六20:30执行，检查本周一到周四的日志并生成周报
    """
    try:
        logger.info("开始执行周报生成任务")

        # 执行自动周报任务
        result = await weekly_report_service.auto_weekly_report_task()

        if result["success"]:
            logger.info("周报生成任务执行成功")

            # 发送成功通知到钉钉机器人
            from app.core.dingtalk_client import global_dingtalk_client
            if global_dingtalk_client:
                success_message = f"""周报自动生成成功

                    任务执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    日志数量: {result['data']['logs_info']['logs_count']}
                    AI总结模式: {result['data']['summary_info']['mode']}
                    钉钉日报ID: {result['data']['send_info']['report_id']}

                周报已自动发送到钉钉，请查收！"""

                # 这里可以添加发送消息到特定群聊的逻辑
                logger.info("周报生成成功通知已准备发送")
        else:
            logger.error(f"周报生成任务失败: {result['message']}")

            # 发送失败通知
            from app.core.dingtalk_client import global_dingtalk_client
            if global_dingtalk_client:
                error_message = f"""周报自动生成失败

失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
失败原因: {result['message']}

请检查系统状态或手动生成周报。"""

                logger.warning("周报生成失败通知已准备发送")

    except Exception as e:
        logger.error(f"周报生成任务异常: {e}")

        # 发送异常通知
        try:
            from app.core.dingtalk_client import global_dingtalk_client
            if global_dingtalk_client:
                exception_message = f"""周报生成任务异常

异常时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
异常信息: {str(e)}

请联系管理员检查系统状态。"""

                logger.error("周报生成异常通知已准备发送")
        except:
            pass  # 避免通知发送失败影响主任务

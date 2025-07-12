#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周报服务模块，整合数据库、AI智能体和钉钉API
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from loguru import logger

from app.db_utils import (
    get_first_user_id, 
    save_weekly_log, 
    update_weekly_log_summary,
    update_weekly_log_dingtalk_id,
    get_weekly_logs_by_date_range,
    get_latest_weekly_log
)
from app.services.ai.weekly_report_agent import weekly_report_agent
from app.services.dingtalk.report_service import dingtalk_report_service


class WeeklyReportService:
    """周报服务类，整合所有周报相关功能"""

    def __init__(self):
        """初始化周报服务"""
        self.ai_agent = weekly_report_agent
        self.dingtalk_service = dingtalk_report_service

    def get_current_week_dates(self) -> tuple[str, str]:
        """
        获取当前周的开始和结束日期
        
        Returns:
            (week_start, week_end) 格式为 'YYYY-MM-DD'
        """
        today = datetime.now()
        # 获取本周一的日期
        monday = today - timedelta(days=today.weekday())
        # 获取本周五的日期
        friday = monday + timedelta(days=4)
        
        return monday.strftime('%Y-%m-%d'), friday.strftime('%Y-%m-%d')

    def get_week_dates_by_offset(self, week_offset: int = 0) -> tuple[str, str]:
        """
        根据偏移量获取周的开始和结束日期
        
        Args:
            week_offset: 周偏移量，0为本周，-1为上周，1为下周
            
        Returns:
            (week_start, week_end) 格式为 'YYYY-MM-DD'
        """
        today = datetime.now()
        # 获取目标周的周一
        target_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        # 获取目标周的周五
        target_friday = target_monday + timedelta(days=4)
        
        return target_monday.strftime('%Y-%m-%d'), target_friday.strftime('%Y-%m-%d')

    async def check_user_weekly_logs(self, user_id: str = None) -> Dict[str, Any]:
        """
        检查用户的周一到周四日志
        
        Args:
            user_id: 用户ID，如果为None则使用第一个用户
            
        Returns:
            包含日志信息的字典
        """
        try:
            # 获取用户ID
            if not user_id:
                user_id = get_first_user_id()
                if not user_id:
                    return {
                        "success": False,
                        "message": "未找到用户信息",
                        "data": None
                    }

            # 获取本周一到周四的日期范围
            week_start, week_end = self.get_current_week_dates()
            # 周四的日期
            thursday = (datetime.strptime(week_start, '%Y-%m-%d') + timedelta(days=3)).strftime('%Y-%m-%d')
            
            # 查询数据库中的日志
            logs = get_weekly_logs_by_date_range(user_id, week_start, thursday)
            
            # 模拟周一到周四的日志内容（如果数据库中没有，创建示例数据）
            if not logs:
                logger.info("数据库中没有找到日志，创建示例数据")
                sample_logs = self._create_sample_weekly_logs(user_id, week_start)
                logs = sample_logs

            # 整合日志内容
            combined_content = self._combine_log_contents(logs)
            
            return {
                "success": True,
                "message": "成功获取周报日志",
                "data": {
                    "user_id": user_id,
                    "week_start": week_start,
                    "week_end": thursday,
                    "logs_count": len(logs),
                    "combined_content": combined_content,
                    "logs": logs
                }
            }

        except Exception as e:
            logger.error(f"检查用户周报日志时发生错误: {e}")
            return {
                "success": False,
                "message": f"检查日志失败: {str(e)}",
                "data": None
            }

    async def generate_weekly_summary(self, raw_content: str, use_quick_mode: bool = False) -> Dict[str, Any]:
        """
        生成周报总结
        
        Args:
            raw_content: 原始日志内容
            use_quick_mode: 是否使用快速模式
            
        Returns:
            包含总结结果的字典
        """
        try:
            logger.info(f"开始生成周报总结，使用{'快速' if use_quick_mode else '标准'}模式")
            
            if use_quick_mode:
                summary = await self.ai_agent.quick_summary(raw_content)
            else:
                summary = await self.ai_agent.generate_weekly_summary(raw_content)
            
            if summary:
                return {
                    "success": True,
                    "message": "周报总结生成成功",
                    "data": {
                        "summary_content": summary,
                        "mode": "quick" if use_quick_mode else "standard"
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "周报总结生成失败",
                    "data": None
                }

        except Exception as e:
            logger.error(f"生成周报总结时发生错误: {e}")
            return {
                "success": False,
                "message": f"生成总结失败: {str(e)}",
                "data": None
            }

    async def create_and_send_weekly_report(self, summary_content: str, user_id: str = None, 
                                          template_id: str = None) -> Dict[str, Any]:
        """
        创建并发送周报到钉钉
        
        Args:
            summary_content: 周报总结内容
            user_id: 用户ID
            template_id: 钉钉日报模版ID
            
        Returns:
            包含发送结果的字典
        """
        try:
            # 获取用户ID
            if not user_id:
                user_id = get_first_user_id()
                if not user_id:
                    return {
                        "success": False,
                        "message": "未找到用户信息",
                        "data": None
                    }

            # 格式化内容为钉钉日报格式
            formatted_contents = self.dingtalk_service.format_weekly_report_content(summary_content)
            
            # 如果没有提供模版ID，使用默认值或查询现有模版
            if not template_id:
                # 这里可以添加查询用户常用模版的逻辑
                template_id = "default_weekly_template"  # 默认模版ID
                logger.warning(f"未提供模版ID，使用默认值: {template_id}")

            # 创建钉钉日报
            report_id = await self.dingtalk_service.create_report(
                user_id=user_id,
                template_id=template_id,
                contents=formatted_contents,
                to_chat=True  # 发送到群聊
            )

            if report_id:
                # 保存到数据库
                week_start, week_end = self.get_current_week_dates()
                log_id = save_weekly_log(
                    user_id=user_id,
                    week_start=week_start,
                    week_end=week_end,
                    log_content="自动生成的周报",
                    summary_content=summary_content,
                    dingtalk_report_id=report_id
                )

                return {
                    "success": True,
                    "message": "周报创建并发送成功",
                    "data": {
                        "report_id": report_id,
                        "log_id": log_id,
                        "user_id": user_id,
                        "template_id": template_id
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "钉钉日报创建失败",
                    "data": None
                }

        except Exception as e:
            logger.error(f"创建并发送周报时发生错误: {e}")
            return {
                "success": False,
                "message": f"发送周报失败: {str(e)}",
                "data": None
            }

    async def auto_weekly_report_task(self) -> Dict[str, Any]:
        """
        自动周报任务（定时任务调用）
        
        Returns:
            任务执行结果
        """
        try:
            logger.info("开始执行自动周报任务")
            
            # 1. 检查用户日志
            log_result = await self.check_user_weekly_logs()
            if not log_result["success"]:
                return log_result

            # 2. 生成周报总结
            raw_content = log_result["data"]["combined_content"]
            summary_result = await self.generate_weekly_summary(raw_content, use_quick_mode=False)
            if not summary_result["success"]:
                return summary_result

            # 3. 创建并发送周报
            summary_content = summary_result["data"]["summary_content"]
            send_result = await self.create_and_send_weekly_report(summary_content)
            
            if send_result["success"]:
                logger.info("自动周报任务执行成功")
                return {
                    "success": True,
                    "message": "自动周报任务执行成功",
                    "data": {
                        "logs_info": log_result["data"],
                        "summary_info": summary_result["data"],
                        "send_info": send_result["data"]
                    }
                }
            else:
                return send_result

        except Exception as e:
            logger.error(f"自动周报任务执行失败: {e}")
            return {
                "success": False,
                "message": f"自动周报任务失败: {str(e)}",
                "data": None
            }

    def _create_sample_weekly_logs(self, user_id: str, week_start: str) -> List[tuple]:
        """
        创建示例周报日志数据
        
        Args:
            user_id: 用户ID
            week_start: 周开始日期
            
        Returns:
            示例日志数据列表
        """
        sample_logs = []
        base_date = datetime.strptime(week_start, '%Y-%m-%d')
        
        # 周一到周四的示例日志
        daily_contents = [
            "周一：完成了项目A的需求分析，与产品经理讨论了功能细节，开始编写技术方案文档。",
            "周二：完成了数据库设计，搭建了开发环境，开始核心功能的开发工作。",
            "周三：完成了用户认证模块，进行了单元测试，修复了发现的几个bug。",
            "周四：完成了API接口开发，与前端同事联调，准备明天的代码评审。"
        ]
        
        for i, content in enumerate(daily_contents):
            log_date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            # 保存到数据库
            log_id = save_weekly_log(
                user_id=user_id,
                week_start=log_date,
                week_end=log_date,
                log_content=content
            )
            
            # 构造返回格式
            sample_logs.append((
                log_id, user_id, log_date, log_date, content, 
                None, None, datetime.now().isoformat(), datetime.now().isoformat()
            ))
        
        return sample_logs

    def _combine_log_contents(self, logs: List[tuple]) -> str:
        """
        整合日志内容
        
        Args:
            logs: 日志数据列表
            
        Returns:
            整合后的日志内容
        """
        if not logs:
            return "本周暂无日志记录。"
        
        combined_parts = []
        for log in logs:
            # log格式: (id, user_id, week_start_date, week_end_date, log_content, ...)
            date = log[2]  # week_start_date
            content = log[4]  # log_content
            combined_parts.append(f"【{date}】{content}")
        
        return "\n\n".join(combined_parts)


# 全局实例
weekly_report_service = WeeklyReportService()

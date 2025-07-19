#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JIRA任务检查和管理服务
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from loguru import logger

from app.core.config import settings
from app.services.dingtalk.card import send_action_card


class JiraTaskService:
    """JIRA任务服务类"""

    def __init__(self, jira_url: Optional[str] = None, username: Optional[str] = None,
                 api_token: Optional[str] = None, project_key: Optional[str] = None):
        self.jira_url = jira_url
        self.username = username
        self.api_token = api_token
        self.project_key = project_key
        self.client = None

    async def initialize(self) -> bool:
        """初始化JIRA客户端"""
        if not all([self.jira_url, self.username, self.api_token]):
            logger.warning("JIRA配置不完整，无法创建JIRA客户端")
            return False

        try:
            # 这里可以初始化真实的JIRA客户端
            logger.info("JIRA客户端初始化成功（模拟）")
            self.client = "jira_client"
            return True
        except Exception as e:
            logger.error(f"JIRA客户端初始化失败: {e}")
            return False

    async def check_tasks_compliance(self) -> Dict[str, Any]:
        """检查任务合规性"""
        if not self.client:
            return {"error": "JIRA客户端未初始化"}

        # 模拟检查逻辑
        return {
            "total_tasks": 10,
            "compliant_tasks": 8,
            "non_compliant_tasks": 2,
            "compliance_rate": 0.8
        }


async def get_jira_client():
    """
    获取JIRA客户端

    Returns:
        JIRA客户端实例，如果配置不完整则返回None
    """
    # 检查是否配置了JIRA相关参数
    if not all([settings.JIRA_URL, settings.JIRA_USERNAME, settings.JIRA_API_TOKEN]):
        logger.warning("JIRA配置不完整，无法创建JIRA客户端")
        return None

    try:
        # 此处为框架实现，实际使用时需要导入jira包并创建JIRA客户端
        # from jira import JIRA
        # jira_client = JIRA(
        #     server=settings.JIRA_URL,
        #     basic_auth=(settings.JIRA_USERNAME, settings.JIRA_API_TOKEN)
        # )
        logger.info("JIRA客户端创建成功（模拟）")
        return "jira_client"
    except Exception as e:
        logger.error(f"创建JIRA客户端异常: {e}")
        return None


async def check_jira_tasks_compliance():
    """
    检查JIRA任务是否符合规范
    """
    logger.info("开始检查JIRA任务合规性")

    # 获取JIRA客户端
    jira_client = await get_jira_client()
    if not jira_client:
        logger.error("无法执行JIRA任务检查：JIRA客户端创建失败")
        return

    try:
        # 设置检查时间范围（最近一周的任务）
        today = datetime.now()
        last_week = today - timedelta(days=7)
        date_str = last_week.strftime("%Y-%m-%d")

        # 查询最近创建的任务
        # 实际实现时，应使用JQL查询
        # issues = jira_client.search_issues(
        #     f'project = {settings.JIRA_PROJECT_KEY} AND created >= {date_str} ORDER BY created DESC'
        # )

        # 模拟一些任务数据进行检查
        issues = [
            {
                "key": "PROJ-123",
                "summary": "实现用户认证功能",
                "assignee": "张三",
                "status": "开发中",
                "due_date": "2025-06-10",
                "description": "详细的任务描述",
                "components": ["后端"],
                "labels": ["认证"]
            },
            {
                "key": "PROJ-124",
                "summary": "修复登录页面样式问题",
                "assignee": "李四",
                "status": "待办",
                "due_date": None,
                "description": "",
                "components": ["前端"],
                "labels": []
            },
            {
                "key": "PROJ-125",
                "summary": "数据库优化",
                "assignee": None,
                "status": "待办",
                "due_date": "2025-06-15",
                "description": "优化数据库性能",
                "components": ["数据库"],
                "labels": ["优化"]
            }
        ]

        # 检查每个任务是否符合规范
        non_compliant_issues = []
        for issue in issues:
            compliance_issues = check_issue_compliance(issue)
            if compliance_issues:
                non_compliant_issues.append({
                    "issue": issue,
                    "compliance_issues": compliance_issues
                })

        # 如果有不合规的任务，发送通知
        if non_compliant_issues:
            await send_compliance_notification(non_compliant_issues)

        logger.info(f"JIRA任务检查完成，发现 {len(non_compliant_issues)} 个不合规任务")

    except Exception as e:
        logger.error(f"检查JIRA任务异常: {e}")


def check_issue_compliance(issue: Dict[str, Any]) -> List[str]:
    """
    检查单个JIRA任务是否符合规范

    Args:
        issue: JIRA任务数据

    Returns:
        List[str]: 不合规原因列表，空列表表示合规
    """
    compliance_issues = []

    # 检查是否有摘要
    if not issue.get("summary"):
        compliance_issues.append("任务缺少摘要")

    # 检查是否有详细描述
    if not issue.get("description"):
        compliance_issues.append("任务缺少详细描述")

    # 检查是否分配给人员
    if not issue.get("assignee"):
        compliance_issues.append("任务未分配给任何人")

    # 检查是否设置了到期日
    if not issue.get("due_date") and issue.get("status") != "完成":
        compliance_issues.append("任务未设置到期日")

    # 检查是否设置了组件
    if not issue.get("components"):
        compliance_issues.append("任务未设置组件")

    # 检查是否设置了标签
    if not issue.get("labels"):
        compliance_issues.append("任务未设置标签")

    return compliance_issues


async def send_compliance_notification(non_compliant_issues: List[Dict[str, Any]]):
    """
    发送任务合规性通知

    Args:
        non_compliant_issues: 不合规任务列表
    """
    try:
        logger.info("发送JIRA任务合规性通知")

        # 构建通知内容
        title = "JIRA任务规范检查结果"

        content = "以下任务需要改进：\n\n"
        for item in non_compliant_issues:
            issue = item["issue"]
            issues = item["compliance_issues"]

            content += f"**{issue['key']} - {issue['summary']}**\n"
            content += f"- 负责人: {issue.get('assignee', '未指定')}\n"
            content += f"- 状态: {issue.get('status', '未知')}\n"
            content += "- 问题:\n"

            for issue_desc in issues:
                content += f"  - {issue_desc}\n"

            content += "\n"

        # 添加动作按钮
        btns = [
            {
                "title": "查看所有任务",
                "url": f"{settings.JIRA_URL}/projects/{settings.JIRA_PROJECT_KEY}/issues"
            }
        ]

        # 为每个不合规任务添加按钮
        for item in non_compliant_issues:
            issue = item["issue"]
            btns.append({
                "title": f"修复 {issue['key']}",
                "url": f"{settings.JIRA_URL}/browse/{issue['key']}"
            })

        # 发送钉钉卡片消息
        # 实际实现时应该发送到特定会话
        conversation_ids = ["mock_conversation_id"]  # 应从配置或数据库获取

        for conv_id in conversation_ids:
            await send_action_card(
                conversation_id=conv_id,
                title=title,
                content=content,
                btns=btns,
                btn_orientation="1"  # 按钮垂直排列
            )

    except Exception as e:
        logger.error(f"发送合规性通知异常: {e}")


async def create_todo_task(assignee: str, issue_key: str, description: str):
    """
    为指定人员创建待办任务

    Args:
        assignee: 负责人
        issue_key: JIRA任务Key
        description: 待办描述
    """
    try:
        logger.info(f"为 {assignee} 创建待办任务: {issue_key}")

        # 实际实现时，应调用钉钉待办API创建待办
        # 此处仅作为框架占位

        # 模拟创建待办
        todo = {
            "assignee": assignee,
            "issue_key": issue_key,
            "description": description,
            "created_at": datetime.now().isoformat()
        }

        logger.info(f"待办任务创建成功: {todo}")
        return todo

    except Exception as e:
        logger.error(f"创建待办任务异常: {e}")
        return None

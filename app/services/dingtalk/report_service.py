#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉日报服务模块，处理钉钉日报相关API调用
"""

import time
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

import httpx
from loguru import logger

from app.core.config import settings


# 延迟导入DingTalkClient以避免循环导入
def get_dingtalk_client():
    from app.core.dingtalk_client import DingTalkClient

    return DingTalkClient


class DingTalkReportService:
    """钉钉日报服务类"""

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """初始化钉钉日报服务"""
        self.base_url = "https://oapi.dingtalk.com"
        self.client_id = client_id or settings.DINGTALK_CLIENT_ID
        self.client_secret = client_secret or settings.DINGTALK_CLIENT_SECRET

    def _get_access_token(self) -> Optional[str]:
        """获取钉钉访问令牌"""
        try:
            # 延迟导入，避免循环导入问题
            def get_global_client():
                from app.core.dingtalk_client import global_dingtalk_client

                return global_dingtalk_client

            # 尝试获取全局客户端
            global_client = get_global_client()
            if global_client:
                return global_client.get_access_token()

            # 如果没有全局客户端，直接调用API
            url = f"{self.base_url}/gettoken"
            params = {"appkey": self.client_id, "appsecret": self.client_secret}

            with httpx.Client() as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("errcode") == 0:
                    return data.get("access_token")
                else:
                    logger.error(f"获取访问令牌失败: {data}")
                    return None

        except Exception as e:
            logger.error(f"获取访问令牌时发生错误: {e}")
            return None

    async def list_reports(
        self,
        user_id: str,
        template_name: str = None,
        start_time: int = None,
        end_time: int = None,
        size: int = 10,
        cursor: str = "0",
    ) -> Optional[Dict]:
        """
        查询日志模版接口

        Args:
            user_id: 用户ID
            template_name: 模版名称
            start_time: 开始时间戳(毫秒)
            end_time: 结束时间戳(毫秒)
            size: 返回数量
            cursor: 游标

        Returns:
            查询结果
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("无法获取访问令牌")
                return None

            url = f"{self.base_url}/topapi/report/list"
            params = {"access_token": access_token}

            # 构建请求体
            data = {"cursor": cursor, "size": size, "userid": user_id}

            if template_name:
                data["template_name"] = template_name
            if start_time:
                data["start_time"] = start_time
            if end_time:
                data["end_time"] = end_time

            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=data)
                response.raise_for_status()
                result = response.json()

                if result.get("errcode") == 0:
                    logger.info(
                        f"查询日志成功，返回 {len(result.get('result', {}).get('data_list', []))} 条记录"
                    )
                    return result.get("result")
                else:
                    logger.error(f"查询日志失败: {result}")
                    return None

        except Exception as e:
            logger.error(f"查询日志时发生错误: {e}")
            return None

    async def get_template_by_name(self, template_name: str, user_id: str) -> Optional[Dict]:
        """
        根据模版名称获取日志模版信息

        Args:
            template_name: 模版名称
            user_id: 用户ID

        Returns:
            模版信息字典，失败返回None
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("无法获取访问令牌")
                return None

            url = f"{self.base_url}/topapi/report/template/getbyname"
            params = {"access_token": access_token}

            data = {"template_name": template_name, "userid": user_id}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=data)
                response.raise_for_status()
                result = response.json()

                if result.get("errcode") == 0:
                    template_info = result.get("result")
                    logger.info(f"获取模版信息成功: {template_name}")
                    return template_info
                else:
                    logger.error(f"获取模版信息失败: {result}")
                    return None

        except Exception as e:
            logger.error(f"获取模版信息时发生错误: {e}")
            return None

    async def save_report_content(
        self, user_id: str, template_id: str, contents: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        保存日志内容

        Args:
            user_id: 用户ID
            template_id: 模版ID
            contents: 日志内容列表

        Returns:
            保存成功返回report_id，失败返回None
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("无法获取访问令牌")
                return None

            url = f"{self.base_url}/topapi/report/savecontent"
            params = {"access_token": access_token}

            data = {
                "create_report_param": {
                    "contents": contents,
                    "dd_from": "report",
                    "template_id": template_id,
                    "userid": user_id,
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=data)
                response.raise_for_status()
                result = response.json()

                if result.get("errcode") == 0:
                    report_id = result.get("result")
                    logger.info(f"保存日志内容成功，report_id: {report_id}")
                    return report_id
                else:
                    logger.error(f"保存日志内容失败: {result}")
                    return None

        except Exception as e:
            logger.error(f"保存日志内容时发生错误: {e}")
            return None

    async def create_report(
        self,
        user_id: str,
        template_id: str,
        contents: List[Dict[str, Any]],
        to_chat: bool = True,
        to_userids: List[str] = None,
        to_cids: str = None,
    ) -> Optional[str]:
        """
        创建日志接口

        Args:
            user_id: 用户ID
            template_id: 模版ID
            contents: 日志内容列表
            to_chat: 是否发送到群聊
            to_userids: 发送给的用户ID列表
            to_cids: 发送到的群聊ID

        Returns:
            创建成功返回report_id，失败返回None
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("无法获取访问令牌")
                return None

            url = f"{self.base_url}/topapi/report/create"
            params = {"access_token": access_token}

            create_param = {
                "contents": contents,
                "dd_from": "weekly_report_bot",
                "template_id": template_id,
                "userid": user_id,
                "to_chat": to_chat,
            }

            if to_userids:
                create_param["to_userids"] = to_userids
            if to_cids:
                create_param["to_cids"] = to_cids

            data = {"create_report_param": create_param}

            logger.info(f"创建日志请求体: {data}")

            # 创建日志
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=data)
                response.raise_for_status()
                result = response.json()

                if result.get("errcode") == 0:
                    report_id = result.get("result")
                    logger.info(f"创建日志成功，report_id: {report_id}")
                    return report_id
                else:
                    logger.error(f"创建日志失败: {result}")
                    return None

        except Exception as e:
            logger.error(f"创建日志时发生错误: {e}")
            return None

    def format_weekly_report_content(
        self, summary_content: str, template_fields: List[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        格式化周报内容为钉钉日报格式

        Args:
            summary_content: AI生成的周报总结内容
            template_fields: 模版字段信息列表

        Returns:
            格式化后的内容列表
        """
        try:
            # 使用模版字段匹配内容，如果没有提供模版字段，则直接抛出错误
            if template_fields:
                return self._format_content_by_template_fields(summary_content, template_fields)

            # 如果没有模版字段, 直接抛出错误
            raise ValueError("未提供模版字段信息")

        except Exception as e:
            logger.error(f"格式化周报内容时发生错误: {e}")
            raise e

    def _format_content_by_template_fields(
        self, summary_content: str, template_fields: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        根据模版字段格式化内容

        Args:
            summary_content: AI生成的周报总结内容
            template_fields: 模版字段信息列表

        Returns:
            格式化后的内容列表
        """
        contents = []

        # 按照模版字段的顺序生成内容
        for field in sorted(template_fields, key=lambda x: x.get("sort", 0)):
            field_name = field.get("field_name", "")
            field_type = field.get("type", 1)
            sort_index = field.get("sort", 0)

            # 尝试匹配内容
            matched_content = summary_content

            if matched_content:
                # 特殊处理包含"上周工作"的字段，转换为列表格式
                if "上周工作" in field_name:
                    # matched_content = self._convert_to_list_format(matched_content)
                    contents.append(
                        {
                            "content_type": "markdown",
                            "sort": str(sort_index),
                            "type": str(field_type),
                            "content": matched_content,
                            "key": field_name,
                        }
                    )
                    continue
                if sort_index == 0:
                    contents.append(
                        {
                            "content_type": "markdown",
                            "sort": str(sort_index),
                            "type": str(field_type),
                            "content": matched_content,
                            "key": field_name,
                        }
                    )
                else:
                    contents.append(
                        {
                            "content_type": "markdown",
                            "sort": str(sort_index),
                            "type": str(field_type),
                            "content": "-",
                            "key": field_name,
                        }
                    )
            else:
                raise ValueError(f"无法匹配到任何内容，字段名称: {field_name}")

        # 如果没有匹配到任何内容，使用默认格式
        if not contents:
            raise ValueError(f"无法匹配到任何内容，字段名称: {field_name}")

        return contents


# 全局实例
dingtalk_report_service = DingTalkReportService()

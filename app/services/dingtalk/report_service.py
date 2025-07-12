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
from app.core.dingtalk_client import DingTalkClient


class DingTalkReportService:
    """钉钉日报服务类"""

    def __init__(self):
        """初始化钉钉日报服务"""
        self.base_url = "https://oapi.dingtalk.com"
        self.client_id = settings.DINGTALK_CLIENT_ID
        self.client_secret = settings.DINGTALK_CLIENT_SECRET

    def _get_access_token(self) -> Optional[str]:
        """获取钉钉访问令牌"""
        try:
            # 使用现有的DingTalkClient获取token
            from app.core.dingtalk_client import global_dingtalk_client
            if global_dingtalk_client:
                return global_dingtalk_client.get_access_token()
            
            # 如果没有全局客户端，直接调用API
            url = f"{self.base_url}/gettoken"
            params = {
                "appkey": self.client_id,
                "appsecret": self.client_secret
            }
            
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

    async def list_reports(self, user_id: str, template_name: str = None, 
                          start_time: int = None, end_time: int = None,
                          size: int = 10, cursor: str = "0") -> Optional[Dict]:
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
            data = {
                "cursor": cursor,
                "size": size,
                "userid": user_id
            }
            
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
                    logger.info(f"查询日志成功，返回 {len(result.get('result', {}).get('data_list', []))} 条记录")
                    return result.get("result")
                else:
                    logger.error(f"查询日志失败: {result}")
                    return None

        except Exception as e:
            logger.error(f"查询日志时发生错误: {e}")
            return None

    async def save_report_content(self, user_id: str, template_id: str, 
                                 contents: List[Dict[str, Any]]) -> Optional[str]:
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
                    "userid": user_id
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

    async def create_report(self, user_id: str, template_id: str, 
                           contents: List[Dict[str, Any]], 
                           to_chat: bool = True, 
                           to_userids: List[str] = None,
                           to_cids: str = None) -> Optional[str]:
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
                "to_chat": to_chat
            }
            
            if to_userids:
                create_param["to_userids"] = to_userids
            if to_cids:
                create_param["to_cids"] = to_cids
            
            data = {"create_report_param": create_param}

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

    def format_weekly_report_content(self, summary_content: str) -> List[Dict[str, Any]]:
        """
        格式化周报内容为钉钉日报格式
        
        Args:
            summary_content: AI生成的周报总结内容
            
        Returns:
            格式化后的内容列表
        """
        try:
            # 解析Markdown内容，提取不同部分
            sections = self._parse_markdown_sections(summary_content)
            
            contents = []
            sort_index = 0
            
            # 本周工作完成情况
            if "本周工作完成情况" in sections or "工作完成" in sections:
                content = sections.get("本周工作完成情况") or sections.get("工作完成", "")
                contents.append({
                    "content_type": "markdown",
                    "sort": str(sort_index),
                    "type": "1",
                    "content": content,
                    "key": "本周工作完成情况"
                })
                sort_index += 1
            
            # 重点项目进展
            if "重点项目进展" in sections or "项目进展" in sections:
                content = sections.get("重点项目进展") or sections.get("项目进展", "")
                contents.append({
                    "content_type": "markdown",
                    "sort": str(sort_index),
                    "type": "1",
                    "content": content,
                    "key": "重点项目进展"
                })
                sort_index += 1
            
            # 问题及解决方案
            if "问题及解决方案" in sections or "问题解决" in sections:
                content = sections.get("问题及解决方案") or sections.get("问题解决", "")
                contents.append({
                    "content_type": "markdown",
                    "sort": str(sort_index),
                    "type": "1",
                    "content": content,
                    "key": "问题及解决方案"
                })
                sort_index += 1
            
            # 下周工作计划
            if "下周工作计划" in sections or "下周计划" in sections:
                content = sections.get("下周工作计划") or sections.get("下周计划", "")
                contents.append({
                    "content_type": "markdown",
                    "sort": str(sort_index),
                    "type": "1",
                    "content": content,
                    "key": "下周工作计划"
                })
                sort_index += 1
            
            # 如果没有找到标准格式，直接使用整个内容
            if not contents:
                contents.append({
                    "content_type": "markdown",
                    "sort": "0",
                    "type": "1",
                    "content": summary_content,
                    "key": "周报总结"
                })
            
            return contents
            
        except Exception as e:
            logger.error(f"格式化周报内容时发生错误: {e}")
            # 返回默认格式
            return [{
                "content_type": "markdown",
                "sort": "0",
                "type": "1",
                "content": summary_content,
                "key": "周报总结"
            }]

    def _parse_markdown_sections(self, content: str) -> Dict[str, str]:
        """
        解析Markdown内容的不同部分
        
        Args:
            content: Markdown内容
            
        Returns:
            解析后的部分字典
        """
        sections = {}
        current_section = None
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 检查是否是标题行
            if line.startswith('#'):
                # 保存上一个部分
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 开始新部分
                current_section = line.lstrip('#').strip()
                current_content = []
            else:
                # 添加到当前部分
                if line:  # 忽略空行
                    current_content.append(line)
        
        # 保存最后一个部分
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections


# 全局实例
dingtalk_report_service = DingTalkReportService()

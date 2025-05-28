#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉卡片消息发送服务
"""

import json
from typing import List, Dict, Any, Optional

from loguru import logger

from app.core.config import settings
from app.core.dingtalk_client import DingTalkClient


async def send_action_card(
    conversation_id: str,
    title: str,
    content: str,
    btns: List[Dict[str, str]],
    btn_orientation: str = "0"
) -> bool:
    """
    发送钉钉交互式卡片消息
    
    Args:
        conversation_id: 会话ID
        title: 卡片标题
        content: 卡片内容（支持markdown格式）
        btns: 按钮列表，格式为[{"title": "按钮文字", "url": "跳转链接"}]
        btn_orientation: 按钮排列方向，0：按钮横向排列，1：按钮纵向排列
        
    Returns:
        bool: 是否发送成功
    """
    try:
        logger.info(f"发送交互卡片消息到会话 {conversation_id}")
        
        # 构建卡片消息参数
        btns_json = []
        for btn in btns:
            btns_json.append({
                "title": btn.get("title", ""),
                "actionURL": btn.get("url", "")
            })
        
        msg_param = {
            "title": title,
            "text": content,
            "btnOrientation": btn_orientation,
            "btns": btns_json
        }
        
        # 创建钉钉客户端实例
        client = DingTalkClient()
        
        # 获取访问令牌
        token = client.get_access_token()
        if not token:
            logger.error("发送卡片消息失败: 无法获取访问令牌")
            return False
        
        # 发送消息
        response = client.send_group_message(
            conversation_id=conversation_id,
            message=json.dumps(msg_param),
            msg_type="actionCard"
        )
        
        return response is not None
        
    except Exception as e:
        logger.error(f"发送卡片消息异常: {e}")
        return False


async def send_feed_card(
    conversation_id: str,
    links: List[Dict[str, str]]
) -> bool:
    """
    发送钉钉图文卡片列表消息
    
    Args:
        conversation_id: 会话ID
        links: 链接列表，格式为[{"title": "标题", "messageURL": "消息链接", "picURL": "图片链接"}]
        
    Returns:
        bool: 是否发送成功
    """
    try:
        logger.info(f"发送图文卡片列表消息到会话 {conversation_id}")
        
        # 构建卡片消息参数
        msg_param = {
            "links": links
        }
        
        # 创建钉钉客户端实例
        client = DingTalkClient()
        
        # 获取访问令牌
        token = client.get_access_token()
        if not token:
            logger.error("发送卡片消息失败: 无法获取访问令牌")
            return False
        
        # 发送消息
        response = client.send_group_message(
            conversation_id=conversation_id,
            message=json.dumps(msg_param),
            msg_type="feedCard"
        )
        
        return response is not None
        
    except Exception as e:
        logger.error(f"发送图文卡片列表消息异常: {e}")
        return False

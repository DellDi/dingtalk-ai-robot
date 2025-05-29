#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉客户端模块，处理与钉钉的连接和消息处理
"""

import time
from typing import Optional

from alibabacloud_dingtalk.oauth2_1_0.client import Client as DingTalkOAuthClient
from alibabacloud_dingtalk.robot_1_0.client import Client as DingTalkRobotClient
from alibabacloud_dingtalk.oauth2_1_0 import models as oauth_models
from alibabacloud_dingtalk.robot_1_0 import models as robot_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from dingtalk_stream import AckMessage, DingTalkStreamClient, Credential, ChatbotHandler, ChatbotMessage
from loguru import logger

from app.core.config import settings
from app.services.ai.handler import AIMessageHandler


class DingTalkClient:
    """钉钉客户端类，管理钉钉Stream连接和消息处理"""

    def __init__(self):
        """初始化钉钉客户端"""
        self.client_id = settings.DINGTALK_CLIENT_ID
        self.client_secret = settings.DINGTALK_CLIENT_SECRET
        self.robot_code = settings.DINGTALK_ROBOT_CODE
        self._token_cache = {"token": None, "expire": 0}
        self.stream_client = None
        self.ai_handler = AIMessageHandler()
        
        # 初始化stream客户端
        self._init_stream_client()
        
    def _init_stream_client(self):
        """初始化钉钉Stream客户端"""
        logger.info("初始化钉钉Stream客户端")
        credential = Credential(self.client_id, self.client_secret)
        self.stream_client = DingTalkStreamClient(credential)
        
        # 注册消息处理器
        self.stream_client.register_callback_handler(
            ChatbotMessage.TOPIC,
            RobotMessageHandler(self)
        )
    
    def get_access_token(self) -> Optional[str]:
        """
        获取钉钉访问令牌，带本地缓存，2小时有效期，提前200秒刷新
        """
        now = time.time()
        if self._token_cache["token"] and now < self._token_cache["expire"]:
            return self._token_cache["token"]
        
        logger.info("获取钉钉访问令牌")
        config = open_api_models.Config(protocol="https", region_id="central")
        client = DingTalkOAuthClient(config)
        
        request = oauth_models.GetAccessTokenRequest(
            app_key=self.client_id,
            app_secret=self.client_secret
        )
        
        try:
            response = client.get_access_token(request)
            token = getattr(response.body, "access_token", None)
            expire_in = getattr(response.body, "expire_in", 7200)
            
            if token:
                self._token_cache["token"] = token
                self._token_cache["expire"] = now + expire_in - 200  # 提前200秒刷新
                return token
        except Exception as e:
            logger.error(f"获取钉钉访问令牌失败: {e}")
        
        return None
    
    def send_group_message(self, conversation_id: str, message: str, msg_type: str = "sampleText"):
        """
        发送群消息
        
        Args:
            conversation_id: 会话ID
            message: 消息内容
            msg_type: 消息类型，默认为文本消息
        """
        token = self.get_access_token()
        if not token:
            logger.error("发送群消息失败: 无法获取访问令牌")
            return None
        
        config = open_api_models.Config(protocol="https", region_id="central")
        client = DingTalkRobotClient(config)
        
        headers = robot_models.OrgGroupSendHeaders()
        headers.x_acs_dingtalk_access_token = token
        
        msg_param = f'{{"content":"{message}"}}'
        
        request = robot_models.OrgGroupSendRequest(
            msg_param=msg_param,
            msg_key=msg_type,
            open_conversation_id=conversation_id,
            robot_code=self.robot_code
        )
        
        try:
            response = client.org_group_send_with_options(
                request,
                headers,
                util_models.RuntimeOptions()
            )
            logger.info(f"消息发送成功: {response.body.request_id}")
            return response
        except Exception as e:
            logger.error(f"发送群消息失败: {e}")
            return None
    
    def start_forever(self):
        """启动钉钉Stream客户端，永久运行"""
        if not self.stream_client:
            self._init_stream_client()
        
        logger.info("启动钉钉Stream客户端")
        self.stream_client.start_forever()
    
    def stop(self):
        """停止钉钉Stream客户端"""
        if self.stream_client:
            logger.info("停止钉钉Stream客户端")
            try:
                # 尝试关闭连接，如果SDK未来支持这个方法
                if hasattr(self.stream_client, 'stop'):
                    self.stream_client.stop()
                # 设置为None以便垃圾回收
                self.stream_client = None
            except Exception as e:
                logger.error(f"停止钉钉Stream客户端异常: {e}")


class RobotMessageHandler(ChatbotHandler):
    """机器人消息处理器"""
    
    def __init__(self, dingtalk_client: DingTalkClient):
        """初始化消息处理器"""
        super(ChatbotHandler, self).__init__()
        self.dingtalk_client = dingtalk_client
        # 直接引用AI处理器，确保它存在
        self.ai_handler = dingtalk_client.ai_handler
        
    async def process(self, callback):
        """处理接收到的消息"""
        try:
            # 解析消息
            incoming_message = ChatbotMessage.from_dict(callback.data)
            logger.info(f"收到消息: {incoming_message.text.content}")
            
            # 获取会话ID
            conversation_id = incoming_message.conversation_id
            sender_id = incoming_message.sender_id
            text_content = incoming_message.text.content
            
            # 处理消息（使用实例变量ai_handler）
            response = await self.ai_handler.process_message(
                text_content, 
                sender_id, 
                conversation_id
            )
            
            # 发送回复 - 正确调用DingTalkClient的方法
            if response:
                # self.dingtalk_client是DingTalkClient实例，而不是DingTalkStreamClient
                # 确保使用正确的方法发送消息
                self.dingtalk_client.send_group_message(conversation_id, response)
            
            return AckMessage.STATUS_OK, "OK"
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            # 使用字符串而非可能不存在的常量
            return "ERROR", str(e)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
钉钉客户端模块，处理与钉钉的连接和消息处理
"""

# 全局钉钉客户端实例，用于在消息处理器中访问
global_dingtalk_client = None

import time
import json
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
from app.services.knowledge.retriever import KnowledgeRetriever # 新增导入
from autogen_core.memory.vector import ChromaDBVectorMemory # 新增导入


class DingTalkClient:
    """钉钉客户端类，管理钉钉Stream连接和消息处理"""

    def __init__(self, knowledge_retriever: Optional[KnowledgeRetriever] = None):
        """初始化钉钉客户端"""
        self.client_id = settings.DINGTALK_CLIENT_ID
        self.client_secret = settings.DINGTALK_CLIENT_SECRET
        self.robot_code = settings.DINGTALK_ROBOT_CODE
        self._token_cache = {"token": None, "expire": 0}
        self.stream_client = None
        
        shared_vector_memory: Optional[ChromaDBVectorMemory] = None
        if knowledge_retriever and knowledge_retriever.initialized:
            shared_vector_memory = knowledge_retriever.vector_memory
            logger.info("DingTalkClient接收到共享的vector_memory")
        else:
            logger.warning("DingTalkClient未接收到有效的共享vector_memory，知识库功能可能受限")
            
        self.ai_handler = AIMessageHandler(vector_memory=shared_vector_memory)

        # 设置全局实例引用，便于其他模块访问
        global global_dingtalk_client
        global_dingtalk_client = self

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
        # 不在这里调用start_forever，避免异步循环冲突

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

    def send_group_message(self, conversation_id: str, message: str, msg_type: str = "sampleMarkdown"):
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

        # 根据消息类型创建消息参数
        if msg_type == "sampleMarkdown":
            msg_param = {"title": "智慧数据机器人", "text": message}
        else:
            msg_param = {"content": message}

        logger.info(f"发送群消息: {msg_param}")
        request = robot_models.OrgGroupSendRequest(
            msg_param=json.dumps(msg_param),
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
            logger.info(f"消息发送成功: {response}")
            return response
        except Exception as e:
            logger.error(f"发送群消息失败: {e}")
            return None

    def send_private_message(self, user_ids: list, message: str, msg_type: str = "sampleMarkdown"):
        """
        发送私聊消息到指定用户

        Args:
            user_ids: 用户ID列表
            message: 消息内容
            msg_type: 消息类型，默认为文本消息

        Returns:
            响应对象或None（失败时）
        """
        token = self.get_access_token()
        if not token:
            logger.error("发送私聊消息失败: 无法获取访问令牌")
            return None

        config = open_api_models.Config(protocol="https", region_id="central")
        client = DingTalkRobotClient(config)

        # 创建请求头
        headers = robot_models.BatchSendOTOHeaders()
        headers.x_acs_dingtalk_access_token = token

        # 根据消息类型创建消息参数
        if msg_type == "sampleMarkdown":
            msg_param = {"title": "智慧数据机器人", "text": message}
        else:
            msg_param = {"content": message}

        logger.info(f"发送私聊消息: {msg_param} 到用户: {user_ids}")

        # 创建请求
        request = robot_models.BatchSendOTORequest(
            robot_code=self.robot_code,
            user_ids=user_ids,
            msg_key=msg_type,
            msg_param=json.dumps(msg_param)
        )

        try:
            response = client.batch_send_otowith_options(
                request,
                headers,
                util_models.RuntimeOptions()
            )
            logger.info(f"私聊消息发送成功: {response}")
            return response
        except Exception as e:
            logger.error(f"发送私聊消息失败: {e}")
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

    def __init__(self, dingtalk_client):
        """初始化消息处理器"""
        super(ChatbotHandler, self).__init__()
        # 将客户端实例存储为类变量
        # 注意：类型提示可能导致错误，移除以避免混淆
        self._client = dingtalk_client

        # 获取AI处理器实例，假设它在dingtalk_client中存在
        if hasattr(dingtalk_client, 'ai_handler'):
            self.ai_handler = dingtalk_client.ai_handler
        else:
            logger.error("未找到AI处理器实例")
            self.ai_handler = None

    async def process(self, callback):
        """处理接收到的消息"""
        try:
            # 解析消息
            incoming_message = ChatbotMessage.from_dict(callback.data)

            # 获取消息信息
            conversation_id = incoming_message.conversation_id
            sender_id = incoming_message.sender_staff_id
            text_content = incoming_message.text.content

            # 判断消息类型（单聊或群聊）
            is_group_chat = conversation_id and not sender_id
            at_users = getattr(incoming_message, "sender_staff_id")
            is_at_robot = len(at_users) > 0
            sender_id = [sender_id] if sender_id else []
            # 日志记录消息类型和内容
            if is_group_chat:
                msg_type = "群聊" + ("（@机器人）" if is_at_robot else "")
            else:
                msg_type = "单聊"
            logger.info(f"收到{msg_type}消息: {text_content} 发送者ID: {sender_id}")

            # 消息处理
            if not self.ai_handler:
                logger.error("无法处理消息：AI处理器未初始化")
                return "ERROR", "系统内部错误"

            response = await self.ai_handler.process_message(
                text_content,
                sender_id,
                conversation_id
            )

            # 发送回复 - 调用全局DingTalkClient实例的方法
            if response:
                from app.core.dingtalk_client import global_dingtalk_client
                if not global_dingtalk_client:
                    logger.error("无法发送消息：全局钉钉客户端未初始化")
                    return "ERROR", "全局客户端未初始化"

                # 根据消息类型选择发送方式
                if is_group_chat:
                    # 群聊回复
                    global_dingtalk_client.send_group_message(conversation_id, response)
                else:
                    # 单聊回复 - 需要用户ID列表
                    global_dingtalk_client.send_private_message(sender_id, response)

            return AckMessage.STATUS_OK, "OK"
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            return "ERROR", str(e)

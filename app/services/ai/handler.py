#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI消息处理器模块，使用AutoGen多智能体实现智能问答
"""

import os
import asyncio
from typing import Optional, Dict, Any, List

from autogen_core.models import ModelFamily
from loguru import logger

# 导入最新的AutoGen v0.5 AgentChat API
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core import CancellationToken

from app.core.config import settings
from app.services.knowledge.retriever import KnowledgeRetriever
from app.services.ai.jira_batch_agent import JiraBatchAgent

class AIMessageHandler:
    """AI消息处理器，基于AutoGen实现多智能体对话"""

    def __init__(self):
        """初始化AI消息处理器"""
        self.knowledge_retriever = KnowledgeRetriever()
        self._setup_api_keys()
        self._init_agents()
        self.conversation_contexts: Dict[str, List[Dict[str, Any]]] = {}
        # 初始化JIRA批处理智能体
        self.jira_batch_agent = JiraBatchAgent()
        self._register_intent_handlers()

    def _setup_api_keys(self):
        """设置API密钥"""
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
            self.is_azure = False
        else:
            logger.warning("未配置任何LLM API密钥，将无法使用AI功能")
            self.is_azure = False

    def _init_agents(self):
        """初始化智能体"""
        model_client = OpenAIChatCompletionClient(
            model="qwen-turbo-latest",
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_info={
                "vision": True,
                "function_calling": True,
                "json_output": False,
                "family": ModelFamily.ANY,
                "structured_output": False,
            },
        )

        # 创建基础助手智能体
        self.assistant = AssistantAgent(
            name="dingtalk",
            system_message="""你是一个专业的钉钉机器人助手，可以：
1. 回答用户的各种问题
2. 从知识库中检索相关信息
3. 帮助用户创建JIRA工单
4. 管理服务器和执行维护任务

请使用简洁、专业、友好的语气回答，尽量提供有价值的信息。
如果需要执行特定任务，请明确告知用户你将如何处理。
""",
            model_client=model_client,
        )

        # 创建用户代理
        self.user_proxy = UserProxyAgent(name="user")  # 不需要人类输入

        # 创建知识库专家智能体
        self.knowledge_agent = AssistantAgent(
            name="knowledge",
            system_message="""你是一个专业的知识库专家，负责从企业知识库中检索信息并提供准确的回答。
当用户询问相关知识时，你会分析问题，并从知识库中找出最相关的信息。
请确保你的回答是基于事实的，并引用信息来源。
""",
            model_client=model_client,
        )

        # 创建服务器管理专家智能体
        self.server_agent = AssistantAgent(
            name="server",
            system_message="""你是一个服务器管理专家，负责：
1. 远程服务器操作和维护
2. Dify服务升级和管理
3. 服务器日志分析和问题诊断

当执行服务器操作时，请确保安全第一，并详细记录执行步骤和结果。
""",
            model_client=model_client,
        )

    def _register_intent_handlers(self):
        """注册意图处理器"""
        self.intent_handlers = {
            "jira": self._handle_jira_intent  # JIRA类型绑定批处理器
        }

    async def _handle_jira_intent(self, message: dict) -> dict:
        """处理JIRA类型请求"""
        return await self.jira_batch_agent.process(message["text"])

    async def process_message(
        self, text: str, sender_id: str, conversation_id: str
    ) -> Optional[str]:
        """处理消息入口"""
        # 意图识别
        intent = self._detect_intent(text)

        # 优先使用注册的意图处理器
        if intent in self.intent_handlers:
            return await self.intent_handlers[intent]({"text": text, "sender_id": sender_id})

        # 默认智能体处理流程
        try:
            logger.info(f"处理来自 {sender_id} 的消息: {text}")

            # 判断消息类型和智能体选择
            if "知识" in text or "查询" in text or "资料" in text:
                # 使用知识库检索信息
                knowledge_results = await self.knowledge_retriever.search(text)

                # 构建上下文增强的消息
                context_message = f"以下是从知识库检索到的信息:\n{knowledge_results}\n\n基于上述信息，请回答用户问题: {text}"

                # 使用知识库专家智能体
                # 注意：v0.5+ API使用on_messages方法
                # 创建消息列表
                messages = [TextMessage(content=context_message, source=self.user_proxy.name)]
                # 发送消息并获取响应
                chat_res = await self.knowledge_agent.on_messages(
                    messages,
                    CancellationToken()
                )

                return self._extract_last_response(chat_res)

            elif "jira" in text.lower() or "工单" in text or "任务" in text:
                # 直接交给批量JIRA智能体（已内置账号处理）
                return await self.jira_batch_agent.process({
                    "text": text,
                    "sender_id": sender_id,
                    "conversation_id": conversation_id
                })

            elif (
                "服务器" in text
                or "升级" in text
                or "dify" in text.lower()
                or "ssh" in text.lower()
            ):
                # 使用服务器专家智能体
                # 创建消息列表
                messages = [TextMessage(content=text, source=self.user_proxy.name)]
                # 发送消息并获取响应
                chat_res = await self.server_agent.on_messages(
                    messages,
                    CancellationToken()
                )

                return self._extract_last_response(chat_res)

            else:
                # 默认使用通用助手智能体
                # 创建消息列表
                messages = [TextMessage(content=text, source=self.user_proxy.name)]
                # 发送消息并获取响应
                chat_res = await self.assistant.on_messages(
                    messages,
                    CancellationToken()
                )

                return self._extract_last_response(chat_res)

        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            return "抱歉，处理您的请求时出现了问题，请稍后再试。"

    def _detect_intent(self, text: str) -> str:
        """意图识别"""
        # TODO: 实现意图识别逻辑
        pass

    def _extract_last_response(self, chat_result) -> str:
        """从聊天结果中提取最后一个回复"""
        try:
            # AutoGen v0.5+ 中，响应是 Response 对象，其中包含 chat_message 属性
            # chat_message 是一个消息对象，包含 content 属性
            if hasattr(chat_result, 'chat_message') and hasattr(chat_result.chat_message, 'content'):
                return chat_result.chat_message.content

            # 兼容旧版API，如果还有chat_history结构
            if hasattr(chat_result, 'chat_history') and chat_result.chat_history:
                # 获取助手的最后一条消息
                for message in reversed(chat_result.chat_history):
                    if hasattr(message, 'role') and message.role == "assistant":
                        return message.content
                    elif hasattr(message, 'source') and message.source.endswith('agent'):
                        return message.content

            logger.warning(f"无法解析聊天结果：{chat_result}")
            return "抱歉，无法获取有效回复。"
        except Exception as e:
            logger.error(f"提取回复异常: {e}")
            return "抱歉，处理回复时出现了问题。"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI消息处理器模块，使用AutoGen多智能体实现智能问答
"""

import os
import asyncio
from typing import Optional, Dict, Any, List

from loguru import logger

# 导入最新的AutoGen v0.5 AgentChat API
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from app.core.config import settings
from app.services.knowledge.retriever import KnowledgeRetriever


class AIMessageHandler:
    """AI消息处理器，基于AutoGen实现多智能体对话"""

    def __init__(self):
        """初始化AI消息处理器"""
        self.knowledge_retriever = KnowledgeRetriever()
        self._setup_api_keys()
        self._init_agents()
        self.conversation_contexts: Dict[str, List[Dict[str, Any]]] = {}

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
        # 配置模型
        if self.is_azure:
            config = {
                "model": settings.AZURE_DEPLOYMENT_NAME or "gpt-4",
                "api_type": "azure",
                "temperature": 0.7,
            }
        else:
            config = {
                "model": "gpt-4o",  # 使用最新模型
                "temperature": 0.7,
            }

        # 创建基础助手智能体
        self.assistant = AssistantAgent(
            name="钉钉助手",
            system_message="""你是一个专业的钉钉机器人助手，可以：
1. 回答用户的各种问题
2. 从知识库中检索相关信息
3. 帮助用户创建JIRA工单
4. 管理服务器和执行维护任务

请使用简洁、专业、友好的语气回答，尽量提供有价值的信息。
如果需要执行特定任务，请明确告知用户你将如何处理。
""",
            model_client=config,
        )

        # 创建用户代理
        self.user_proxy = UserProxyAgent(name="用户")  # 不需要人类输入

        # 创建知识库专家智能体
        self.knowledge_agent = AssistantAgent(
            name="知识库专家",
            system_message="""你是一个专业的知识库专家，负责从企业知识库中检索信息并提供准确的回答。
当用户询问相关知识时，你会分析问题，并从知识库中找出最相关的信息。
请确保你的回答是基于事实的，并引用信息来源。
""",
            model_client=config,
        )

        # 创建JIRA工单专家智能体
        self.jira_agent = AssistantAgent(
            name="JIRA专家",
            system_message="""你是一个JIRA工单管理专家，负责：
1. 帮助用户创建JIRA工单
2. 检查JIRA工单是否符合规范
3. 分配任务和创建待办

当需要处理JIRA相关请求时，请确保获取所有必要信息，包括标题、描述、优先级等。
""",
            model_client=config,
        )

        # 创建服务器管理专家智能体
        self.server_agent = AssistantAgent(
            name="服务器专家",
            system_message="""你是一个服务器管理专家，负责：
1. 远程服务器操作和维护
2. Dify服务升级和管理
3. 服务器日志分析和问题诊断

当执行服务器操作时，请确保安全第一，并详细记录执行步骤和结果。
""",
            model_client=config,
        )

    async def process_message(
        self, text: str, sender_id: str, conversation_id: str
    ) -> Optional[str]:
        """
        处理接收到的消息，使用AutoGen多智能体生成回复

        Args:
            text: 消息文本内容
            sender_id: 发送者ID
            conversation_id: 会话ID

        Returns:
            Optional[str]: 生成的回复，如果处理失败则返回None
        """
        try:
            logger.info(f"处理来自 {sender_id} 的消息: {text}")

            # 判断消息类型和智能体选择
            if "知识" in text or "查询" in text or "资料" in text:
                # 使用知识库检索信息
                knowledge_results = await self.knowledge_retriever.search(text)

                # 构建上下文增强的消息
                context_message = f"以下是从知识库检索到的信息:\n{knowledge_results}\n\n基于上述信息，请回答用户问题: {text}"

                # 使用知识库专家智能体
                # 注意：v0.5+ API使用chat方法而不是initiate_chat
                chat_res = await self.user_proxy.on_messages(
                    self.knowledge_agent,
                    message=context_message,
                )

                return self._extract_last_response(chat_res)

            elif "jira" in text.lower() or "工单" in text or "任务" in text:
                # 使用JIRA专家智能体
                chat_res = await self.user_proxy.chat(
                    self.jira_agent,
                    message=text,
                )

                return self._extract_last_response(chat_res)

            elif (
                "服务器" in text
                or "升级" in text
                or "dify" in text.lower()
                or "ssh" in text.lower()
            ):
                # 使用服务器专家智能体
                chat_res = await self.user_proxy.chat(
                    self.server_agent,
                    message=text,
                )

                return self._extract_last_response(chat_res)

            else:
                # 默认使用通用助手智能体
                chat_res = await self.user_proxy.chat(
                    self.assistant,
                    message=text,
                )

                return self._extract_last_response(chat_res)

        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            return "抱歉，处理您的请求时出现了问题，请稍后再试。"

    def _extract_last_response(self, chat_result) -> str:
        """从聊天结果中提取最后一个回复"""
        try:
            # 获取助手的最后一条消息
            for message in reversed(chat_result.chat_history):
                if message.role == "assistant":
                    return message.content

            return "抱歉，无法获取有效回复。"
        except Exception as e:
            logger.error(f"提取回复异常: {e}")
            return "抱歉，处理回复时出现了问题。"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI消息处理器模块，使用AutoGen SelectorGroupChat多智能体实现智能问答和意图识别
"""

import os
import asyncio
from autogen_agentchat.base import TaskResult
from loguru import logger
from typing import Optional, Dict, Any, List, Union

from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui import Console
from autogen_ext.memory.chromadb import ChromaDBVectorMemory # Added import

from app.core.config import settings
from app.services.ai.jira_batch_agent import JiraBatchAgent
from app.services.ai.openai_client import get_openai_client

# --- Selector Prompt ---# 
SELECTOR_PROMPT_ZH = """你是一个智能路由选择器。根据用户的最新请求内容，从以下可用智能体中选择最合适的一个来处理该请求。
请仔细阅读智能体的描述，确保选择最相关的智能体。

可用智能体 (格式: <名称> : <描述>):
{roles}

对话历史 (最近几条):
{history}

请仔细阅读最新的用户请求，并仅选择一个最能胜任该任务的智能体名称。不要添加任何解释或额外文字，只需给出智能体名称。
选择的智能体:"""


class AIMessageHandler:
    """AI消息处理器，基于AutoGen SelectorGroupChat实现多智能体对话和意图识别"""

    def __init__(self, vector_memory: Optional[ChromaDBVectorMemory] = None):
        """初始化AI消息处理器"""
        self.shared_vector_memory = vector_memory
        if self.shared_vector_memory:
            logger.info("AIMessageHandler initialized with shared vector_memory.")
        else:
            logger.warning("AIMessageHandler initialized without shared vector_memory. Knowledge base functionality will be limited.")
        
        self.jira_batch_agent = JiraBatchAgent() # JIRA批处理实例
        self._setup_api_keys()
        self.model_client = get_openai_client(model_info={"json_output": False})
        self._init_agents_and_groupchat()

        self._current_sender_id: Optional[str] = None
        self._current_conversation_id: Optional[str] = None

    def _setup_api_keys(self):
        """设置API密钥"""
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        elif settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_API_BASE: # Check for Azure keys
            logger.info("Azure OpenAI API key found, assuming environment variables are set for AutoGen.")
        else:
            logger.warning("未配置任何LLM API密钥，AI功能可能受限或无法使用")

    async def _search_knowledge_base_tool(self, query: str, n_results: int = 3) -> str:
        """工具函数：用于知识库检索，使用共享的vector_memory"""
        logger.info(f"工具: _search_knowledge_base_tool 调用，查询: {query}")
        if not self.shared_vector_memory:
            logger.warning("_search_knowledge_base_tool: shared_vector_memory is not available.")
            return "知识库未正确配置或初始化，无法执行搜索。"

        try:
            # ChromaDBVectorMemory.retrieve_docs is synchronous
            retrieved_docs_dict = await asyncio.to_thread(
                self.shared_vector_memory.retrieve_docs,
                query_texts=[query],
                n_results=n_results,
                # include=["metadatas", "documents"] # Ensure documents are included if needed by processing
            )
            
            # Process results (this part might need adjustment based on actual structure of retrieved_docs_dict)
            # Assuming retrieved_docs_dict is like: {'ids': [['id1']], 'documents': [['doc1_content']], 'metadatas': [[{'source': 'src1'}]]}
            # And we want to return a string representation of the documents
            processed_results = []
            if retrieved_docs_dict and retrieved_docs_dict.get("documents"):
                # The result for a single query is the first element in the list of lists
                docs_for_query = retrieved_docs_dict["documents"][0]
                metadatas_for_query = retrieved_docs_dict.get("metadatas", [[]])[0]
                
                for i, doc_content in enumerate(docs_for_query):
                    metadata_info = metadatas_for_query[i] if i < len(metadatas_for_query) else {}
                    source = metadata_info.get("source", "未知来源")
                    processed_results.append(f"来源: {source}\n内容: {doc_content}") 
            
            if not processed_results:
                return "未在知识库中找到相关信息。"
            
            return "\n\n---\n\n".join(processed_results)
        except Exception as e:
            logger.error(f"Error during knowledge base search: {e}")
            return f"知识库检索时发生错误: {e}"

    async def _process_jira_request_tool(self, request_text: str) -> str:
        """工具函数：用于处理JIRA请求"""
        logger.info(f"工具: _process_jira_request_tool 调用，请求文本: {request_text}")

        message_payload = {
            "text": request_text,
            "sender_id": self._current_sender_id or "unknown_sender",
            "conversation_id": self._current_conversation_id or "unknown_conversation"
        }
        response_data = await self.jira_batch_agent.process(message_payload)

        if isinstance(response_data, dict) and "content" in response_data:
            return str(response_data["content"])
        elif isinstance(response_data, str):
            return response_data

        logger.warning(f"JiraBatchAgent (通过工具) 返回了非标准格式: {response_data}")
        return "JIRA任务已提交处理，但响应格式无法直接转换为文本。"

    def _init_agents_and_groupchat(self):
        """初始化智能体和 SelectorGroupChat"""

        # self.user_proxy = UserProxyAgent(
        #     name="UserProxy",
        #     description="一个代理，可以执行代码和调用提供的工具函数，例如知识库搜索或JIRA操作。",
        # )

        # self.indent_agent = AssistantAgent(
        #     "PlanningAgent",
        #     description="一个意图识别智能体，负责识别用户意图并选择合适的智能体处理。",
        #     model_client=self.model_client,
        #     system_message="""
        #     你是一个意图识别智能体，负责识别用户意图并选择合适的智能体处理。
        #     你的团队成员包括：
        #         KnowledgeExpert: 知识库专家
        #         ServerAdmin: 服务器管理专家
        #         JiraSpecialist: JIRA任务专家
        #         GeneralAssistant: 通用助手-日常问题

        #     你只识别用户意图并选择合适的智能体，不亲自执行。

        #     补充团队成员命中关键词拓展：
        #     KnowledgeExpert: 命中关键词拓展：1. 你是谁？2. 曾迪是谁？

        #     当识别出用户意图后，请使用以下格式：
        #     1. <agent> : <task>

        #     当识别出用户意图后，请总结发现并以 "TERMINATE" 结束你的回复。
        #     """,
        # )

        self.knowledge_expert_agent = AssistantAgent(
            name="KnowledgeExpert",
            system_message="你是一个知识库专家。如果用户的问题需要从知识库中查找答案，请调用`search_knowledge_base`工具，并使用用户原始提问作为查询参数。根据工具返回的结果回答用户。如果工具未返回有效信息，请告知用户知识库中没有相关内容。回答完毕后，请以'TERMINATE'结束你的回复。",
            description="知识库专家：当用户提问公司产品、文档、政策或历史数据等需要查阅内部资料的问题时，选择我。我会使用知识库工具查找答案。",
            model_client=self.model_client,
            memory=[self.shared_vector_memory],  # Use shared vector memory as list per autogen v0.6 API
        )

        self.server_admin_agent = AssistantAgent(
            name="ServerAdmin",
            system_message="你是一个服务器管理专家。负责回答关于服务器操作、Dify服务管理、SSH连接、日志分析等问题。请提供建议和信息，不要实际执行任何服务器命令。回答完毕后，请以'TERMINATE'结束你的回复。",
            description="服务器管理专家：当用户咨询服务器维护、Dify平台管理、SSH操作或日志分析等技术问题时，选择我。",
            model_client=self.model_client,
        )

        self.jira_specialist_agent = AssistantAgent(
            name="JiraSpecialist",
            system_message="""
            你是一个JIRA任务专家。如果用户想要创建JIRA工单/任务，请调用`_process_jira_request_tool`工具，并将用户的完整原始请求作为参数。根据工具返回的结果回复用户。
            无论调用工具成功失败，你不能遗漏任何工具的信息，最后的回复始终以添加'TERMINATE'结束。
            """,
            tools=[self._process_jira_request_tool],
            description="JIRA任务专家：当用户的请求明确涉及JIRA、创建工单时，选择我。我会使用JIRA工具处理请求。",
            model_client=self.model_client,
        )

        self.general_assistant_agent = AssistantAgent(
            name="GeneralAssistant",
            system_message="""
            你是一个通用的AI助手。负责回答引导用户，或进行闲聊，查看天气等等。
            你可以告诉用户你会什么技能包括：
            1. 服务器管理
            ```
             dify服务重启
             dify服务自动化升级
             系统运行状态查询
            ```
            2. 数据技术知识查询
            3. JIRA需求提单：告诉用户提单格式要求：
            ```
                配置jira信息
                **用户名**: `your_jira_username`
                **密码**: `your_jira_password` 
                
            ```
            格式要求：
            ```
            1. 需求描述中最好包含客户名称的相关信息
            2. 不限制内容，但要确保信息基本可用
            3. 默认批量提单，如果不需要批量，请在描述中体现
            ```
            
            回答完毕后，请以'TERMINATE'结束你的回复。
            """,
            description="通用助手：对于日常对话、一般性问题选择我。",
            model_client=self.model_client,
            # tools=[self._process_weather_request_tool],
        )

        selectable_agents = [
            # self.indent_agent,
            self.knowledge_expert_agent,
            self.server_admin_agent,
            self.jira_specialist_agent,
            self.general_assistant_agent,
        ]

        text_mention_termination = TextMentionTermination("TERMINATE")
        max_messages_termination = MaxMessageTermination(max_messages=25)

        self.groupchat = SelectorGroupChat(
            participants=selectable_agents,
            selector_prompt=SELECTOR_PROMPT_ZH,
            model_client=self.model_client,
            allow_repeated_speaker=True,
            termination_condition=text_mention_termination | max_messages_termination,
        )

    async def process_message(
        self, text: str, sender_id: str, conversation_id: str
    ) -> Optional[str]:
        """使用SelectorGroupChat处理传入的消息"""
        logger.info(f"AIMessageHandler 收到消息 from {sender_id}: {text}")
        self._current_sender_id = sender_id
        self._current_conversation_id = conversation_id

        final_reply = "抱歉，处理您的请求时出现了问题，未能获取明确回复。"

        try:
            team = self.groupchat

            # result = await Console(team.run_stream(task=text))

            # result = await team.run(task=text)

            result = TaskResult(messages=[])

            async for message in team.run_stream(task=text):
                result.messages.append(message)

            if not result or not hasattr(result, "messages") or not result.messages:
                logger.error("SelectorGroupChat: 团队处理失败或未返回任何消息。")
                return "抱歉，处理您的请求时出现了问题，未能获取明确回复。"

            # result.messages[-1] 被理解为一个容器对象
            # 这个容器对象的字符串表示形式与INFO日志中的 "messages=[...] stop_reason=..." 相符
            final_reply_container = result.messages[-1]

            # 记录一下这个容器对象，以便调试确认
            # logger.info(f"SelectorGroupChat 最终回复容器对象: {final_reply_container}")

            actual_final_message = None
            # 从容器中提取真正的最后一条消息
            if hasattr(final_reply_container, 'messages') and isinstance(final_reply_container, TaskResult) and final_reply_container.messages:
                actual_final_message = final_reply_container.messages[-1]
                logger.info(f"SelectorGroupChat 从容器提取的实际最终消息: {actual_final_message}")
            else:
                # 如果容器结构不符合预期，或者没有消息，则记录错误
                logger.error(
                    f"SelectorGroupChat: 最终回复容器对象结构不符合预期或其消息列表为空. 类型: {type(final_reply_container)}"
                )
                return "抱歉，处理您的请求时出现了问题，未能获取最终回复。"

            # 现在，actual_final_message 应该是我们期望的 TextMessage 对象
            # 对它进行验证
            if (
                not isinstance(actual_final_message, TextMessage)
                or not actual_final_message.content
            ):
                logger.error(
                    f"SelectorGroupChat: 提取的实际最终消息无效或为空. "
                    f"类型: {type(actual_final_message)}, 内容: {getattr(actual_final_message, 'content', 'N/A')}"
                )
                return "抱歉，处理您的请求时出现了问题，未能获取明确回复。"

            # 使用提取出来的实际消息内容
            final_reply_content = actual_final_message.content
            if final_reply_content and "TERMINATE" in final_reply_content:
                final_reply_content = final_reply_content.replace("TERMINATE", "").strip()

            if not final_reply_content or final_reply_content.lower() == "none":
                final_reply_content = "已处理您的请求，但未生成明确的文本回复。"

            return final_reply_content

        except Exception as e:
            logger.error(f"处理消息时发生异常: {e}", exc_info=True)
            final_reply = f"抱歉，处理您的请求时发生错误: {e}"

        finally:
            self._current_sender_id = None
            self._current_conversation_id = None

        logger.info(f"AIMessageHandler 回复: {final_reply}")
        return final_reply

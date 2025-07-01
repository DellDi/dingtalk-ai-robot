#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI消息处理器模块，使用AutoGen SelectorGroupChat多智能体实现智能问答和意图识别
"""

import os
import asyncio
from autogen_agentchat.base import TaskResult
from loguru import logger
from typing import Optional

from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui import Console
from autogen_ext.memory.chromadb import ChromaDBVectorMemory  # Added import

from app.core.config import settings

from app.services.ai.openai_client import get_openai_client
from app.services.ai.tools import (
    process_weather_request,
    search_knowledge_base,
    process_jira_request,
    process_ssh_request,
)


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
            logger.warning(
                "AIMessageHandler initialized without shared vector_memory. Knowledge base functionality will be limited."
            )

        self._setup_api_keys()
        self.model_client = get_openai_client(model_info={"json_output": False})
        self._init_agents_and_groupchat()

        self._current_sender_id: Optional[str] = None
        self._current_conversation_id: Optional[str] = None

    def _setup_api_keys(self):
        """设置API密钥"""
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        else:
            logger.warning("未配置任何LLM API密钥，AI功能可能受限或无法使用")

    async def _search_knowledge_base_tool(self, query: str, n_results: int = 3) -> str:
        """知识库检索工具（薄封装，实际逻辑在 tools.knowledge_base）"""
        return await search_knowledge_base(self.shared_vector_memory, query, n_results)

    async def _process_jira_request_tool(self, request_text: str) -> str:
        """JIRA 请求工具（薄封装，实际逻辑在 tools.jira）"""
        return await process_jira_request(
            request_text,
            sender_id=self._current_sender_id or "unknown_sender",
            conversation_id=self._current_conversation_id or "unknown_conversation",
        )

    async def _process_ssh_request_tool(
        self,
        request_text: str,
        host: str = None,
        mode: str = "free"
    ) -> str:
        """SSH请求工具（薄封装，实际逻辑在 tools.ssh）"""
        # 使用配置中的默认主机或用户指定的主机
        target_host = host or settings.SSH_DEFAULT_HOST or "default-server"
        logger.info(f"[SSH-CONFIG-DEBUG] settings.SSH_DEFAULT_HOST = {settings.SSH_DEFAULT_HOST}")
        logger.info(f"[SSH-CONFIG-DEBUG] 最终使用的主机地址: {target_host}")
        logger.info(f"工具: _process_ssh_request_tool 调用，request_text={request_text}, host={target_host}, mode={mode}")
        try:
            return await process_ssh_request(
                request_text,
                target_host,
                mode=mode,
                sender_id=self._current_sender_id or "unknown_sender",
                conversation_id=self._current_conversation_id or "unknown_conversation",
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"SSH请求工具调用失败: {e}")
            return f"❌ 无法执行SSH操作: {e}"

    async def _process_weather_request_tool(
        self,
        *,
        city: str,
        data_type: str = "current",
        days: int | None = None,
        hours: int | None = None,
        dt: int | None = None,
        date: str | None = None,
    ) -> str:
        """天气查询工具薄封装，直接转调 `tools.weather.process_weather_request`。

        参数
        ----
        city: 中文地区名称或者拼音城市名，例如 "杭州" 或 "Hangzhou"（首字母大写）。
        data_type: 要查询的数据类型：`当前`current``|`分钟级`minutely``|`小时级`hourly``|`日级`daily``|`历史`historical``。
        days: 当 ``data_type='daily'`` 时，返回天数 (1-7)。
        hours: 当 ``data_type='hourly'`` 时，返回小时数 (1-48)。
        dt: 当 ``data_type='historical'`` 时，Unix 时间戳（秒）。若提供则优先生效。
        date: 当 ``data_type='historical'`` 时，也可直接传形如 ``YYYY-MM-DD`` 的日期字符串，工具内部转换为 00:00 (Asia/Shanghai) 对应 UTC 秒数。
             二者同时提供时以 ``dt`` 优先。若均未提供则默认回溯 24 小时。
        """
        logger.info(
            f"工具: _process_weather_request_tool 调用，city={city}, data_type={data_type}, days={days}, hours={hours}, dt={dt}, date={date}"
        )
        try:
            return await process_weather_request(
                city=city,
                data_type=data_type,
                days=days,
                hours=hours,
                dt=dt,
                date=date,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"天气查询工具调用失败: {e}")
            return f"❌ 无法获取天气信息: {e}"

    def _init_agents_and_groupchat(self):
        """初始化智能体和 SelectorGroupChat"""

        self.knowledge_expert_agent = AssistantAgent(
            name="KnowledgeExpert",
            system_message="""你是一个知识库专家。如果用户的问题需要从知识库中查找答案，请调用`search_knowledge_base`工具，并使用用户原始提问作为查询参数。

            **重要的回复格式要求：**
            1. 必须先调用知识库工具获取搜索结果
            2. 根据工具返回的结果回答用户问题
            3. 如果工具未返回有效信息，请告知用户知识库中没有相关内容
            4. 最后在回复末尾添加'TERMINATE'

            绝对不要只返回'TERMINATE'而不包含搜索结果或回答！""",
            description="知识库专家：当用户提问公司产品、文档、政策或历史数据等需要查阅内部资料的问题时，选择我。我会使用知识库工具查找答案。",
            model_client=self.model_client,
            memory=[
                self.shared_vector_memory
            ],  # Use shared vector memory as list per autogen v0.6 API
        )

        self.server_admin_agent = AssistantAgent(
            name="ServerAdmin",
            system_message="""你是一个服务器管理专家。负责处理服务器操作、Dify服务管理、SSH连接、日志分析等问题。

            当用户请求涉及以下内容时，必须调用`_process_ssh_request_tool`工具：
            1. 查看服务器状态（磁盘、内存、进程等）
            2. 需要操作服务器，执行相关的服务器命令的时候
            3. Dify服务升级或维护

            工具参数说明：
            - request_text: 用户原始请求文本
            - host: 目标主机地址（默认传空）
            - mode: 操作模式 (free/upgrade)

            特别注意：
            - 对于明确的Dify升级请求，必须使用mode='upgrade'
            - 其他SSH操作使用mode='free'
            - 不要直接给出建议，必须调用工具获取实际执行结果

            **重要的回复格式要求：**
            1. 必须先调用SSH工具获取执行结果
            2. 然后将工具返回的完整结果直接作为你的回复内容
            3. 不要省略、修改或总结工具返回的任何信息
            4. 最后在回复末尾添加'TERMINATE'

            回复流程：
            1. 调用_process_ssh_request_tool工具
            2. 直接输出工具返回的完整内容
            3. 添加TERMINATE

            绝对不要只返回'TERMINATE'而不包含工具执行结果！
            绝对不要使用占位符文本如'[SSH工具返回的完整结果]'！""",
            description="服务器管理专家：当用户咨询服务器维护、Dify平台管理、SSH操作或日志分析等技术问题时，选择我。我会实际执行相关命令。",
            model_client=self.model_client,
            tools=[self._process_ssh_request_tool],
        )

        self.jira_specialist_agent = AssistantAgent(
            name="JiraSpecialist",
            system_message="""你是一个JIRA任务专家。如果用户想要创建JIRA工单/任务，请调用`_process_jira_request_tool`工具，并将用户的完整原始请求作为参数。

            **重要的回复格式要求：**
            1. 必须先调用JIRA工具处理用户请求
            2. 将工具返回的完整结果作为你的回复内容
            3. 不要省略或修改工具返回的任何信息
            4. 无论工具调用成功或失败，都要包含完整的工具信息
            5. 最后在回复末尾添加'TERMINATE'

            绝对不要只返回'TERMINATE'而不包含工具执行结果！""",
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
             天气查询、支持、当前、近七天、支持历史查询
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
            ---
            你的回答尽量整理成一个标准markdown格式的文档，语言风趣幽默。按照回复、需求、问题、建议等不同的场景，支持多种丰富的markdown语法，如：
            ```
            1. **加粗**
            2. *斜体*
            3. `代码`
            4. [链接](https://www.example.com)
            5. ![图片](https://www.example.com/image.png)
            6. 表格
            7. 列表
            8. mermaid图表
            9. 互联网风格icon
            ```
            如果你的得到的信息有来源，请标明来源。

            回答完毕后，请以'TERMINATE'结束你的回复。
            """,
            description="通用助手：对于日常对话、一般性问题，天气问题选择我。",
            model_client=self.model_client,
            tools=[self._process_weather_request_tool],
        )

        selectable_agents = [
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
            if (
                hasattr(final_reply_container, "messages")
                and isinstance(final_reply_container, TaskResult)
                and final_reply_container.messages
            ):
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

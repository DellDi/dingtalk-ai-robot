#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周报总结智能体模块，基于AutoGen RoundRobinGroupChat实现智能周报生成
"""

import asyncio
from typing import Optional
from loguru import logger

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage

from app.services.ai.client.openai_client import get_openai_client, get_gemini_client

class WeeklyReportAgent:
    """周报总结智能体，使用双智能体协作生成高质量周报"""

    def __init__(self):
        """初始化周报智能体"""
        self.model_client = get_openai_client(model_info={"json_output": False})
        self.gemini_model_client = get_gemini_client(model_info={"json_output": False})
        self._init_agents_and_groupchat()

    def _init_agents_and_groupchat(self):
        """初始化智能体和群聊"""
        # 1. 创建总结智能体 (Summarizer Agent)
        self.summarizer_agent = AssistantAgent(
            name="Summarizer",
            description="""你是一个专业的周报总结者。
            你的任务是根据用户提供的原始文本，生成一份正式、段落有序、且完全没有"AI味"的周报总结。
            请确保总结内容简洁明了，突出重点，并使用正式的、类似研发人员的描述。

            周报格式要求：
            1. 使用Markdown格式输出
            2. 无需包含大标题和小总结：比如说"周报总结"等字样。
            3. 语言正式、简洁、专业、研发
            4. 避免使用AI生成内容的常见表达
            5. 要有重点的开头加粗和冒号，但是要随意一些，不要过分对仗工整
            6. 三级标题开始即可、只能使用三级标题和四级标题
            """,
            model_client=self.model_client,
        )

        # 2. 创建检察官智能体 (Reviewer Agent) - 使用Gemini大模型
        self.reviewer_agent = AssistantAgent(
            name="Reviewer",
            description="""你是一个周报检察官。
            你的任务是审查Summarizer生成的周报总结。
            请检查以下几点：
            1. 格式：段落是否清晰有序？是否符合Markdown格式？
            2. 语法：是否存在语法错误或拼写错误？拆分的条目和场景是否有重点的开头加粗和冒号？
            3. 正式性：语言是否正式，符合普通开发人员写的周报？
            4. "AI味"：是否完全去除了AI生成内容的痕迹，听起来像人类撰写？
            5. 不要包含大标题：比如说"周报总结"等字样
            6. 只能使用三级标题和四级标题

            如果总结不符合要求，请明确指出问题所在，并提供具体的修改建议。

            如果周报内容基本上符合要求，请回复以下特定短语来批准并结束任务：
            "FINAL_REPORT_APPROVED: [这里是最终的周报总结内容]"
            """,
            model_client=self.gemini_model_client,
        )

        # 3. 设置终止条件
        # 当 Reviewer Agent 的消息中包含 "FINAL_REPORT_APPROVED:" 时，对话终止
        termination_condition = TextMentionTermination("FINAL_REPORT_APPROVED:")

        # 4. 创建 RoundRobinGroupChat（简化终止条件）
        self.group_chat = RoundRobinGroupChat(
            [self.summarizer_agent, self.reviewer_agent],
            termination_condition=termination_condition,
            max_turns=6,  # 最多允许 6 轮交互：3轮总结+3轮审查
        )

    async def generate_weekly_summary(self, raw_log_content: str) -> Optional[str]:
        """
        生成周报总结

        Args:
            raw_log_content: 原始日志内容

        Returns:
            生成的周报总结内容，如果失败返回None
        """
        try:
            logger.info("开始生成周报总结")

            # 构建任务提示
            task_prompt = f"""

原始内容：
{raw_log_content}

要求：
1. 及时输出终止条件，不要超过三轮审核的过程
2. 最终只输出Markdown格式的周报总结，无需其他说明
"""

            # 运行智能体团队
            stream = self.group_chat.run_stream(task=task_prompt)

            # 收集所有消息
            messages = []
            async for message in stream:
                messages.append(message)
                if isinstance(message, TextMessage):
                    logger.debug(f"[{message.source}]: {message.content[:100]}...")

            # 查找最终的周报总结（优先使用Reviewer的输出，其次是Summarizer的输出）
            final_summary = None

            # 首先查找Reviewer的最后一个有效输出
            for message in reversed(messages):
                if (
                    isinstance(message, TextMessage)
                    and message.source == "Reviewer"
                    and message.content.strip()
                    and not message.content.strip().upper().startswith("TERMINATE")
                ):
                    final_summary = message.content.strip()
                    logger.info("使用Reviewer审查后的周报总结")
                    break

            # 如果没有找到Reviewer的有效输出，使用Summarizer的最后输出
            if not final_summary:
                for message in reversed(messages):
                    if (
                        isinstance(message, TextMessage)
                        and message.source == "Summarizer"
                        and message.content.strip()
                        and not message.content.strip().upper().startswith("TERMINATE")
                    ):
                        final_summary = message.content.strip()
                        logger.info("使用Summarizer的周报总结")
                        break

            if final_summary:
                # 清理可能的markdown代码块标记
                if final_summary.startswith("```markdown"):
                    final_summary = final_summary.replace("```markdown", "").strip()
                if final_summary.endswith("TERMINATE"):
                    final_summary = final_summary.replace("TERMINATE", "").strip()

                logger.info("周报总结生成成功")
                return final_summary
            else:
                logger.warning("未能生成有效的周报总结")
                return None

        except Exception as e:
            logger.error(f"生成周报总结时发生错误: {e}")
            return None

    async def quick_summary(self, raw_log_content: str) -> Optional[str]:
        """
        快速生成周报总结（单智能体模式）

        Args:
            raw_log_content: 原始日志内容

        Returns:
            生成的周报总结内容
        """
        try:
            logger.info("开始快速生成周报总结")

            # 使用单个智能体快速生成
            quick_agent = AssistantAgent(
                name="QuickSummarizer",
                description="""你是一个高效的周报总结专家。请根据提供的原始日志内容，快速生成一份专业的周报总结。

                格式要求：
                1. 使用Markdown格式
                2. 包含：本周完成工作、重点项目进展、问题解决、下周计划
                3. 语言正式、简洁、专业
                4. 突出重点和成果
                """,
                model_client=self.model_client,
            )

            # 构建任务提示
            task_prompt = f"""
请根据以下原始日志内容生成一份专业的周报总结：

{raw_log_content}

请直接输出Markdown格式的周报总结，无需其他说明。
"""

            # 发送消息并获取回复
            from autogen_agentchat.messages import TextMessage

            response = await quick_agent.on_messages(
                [TextMessage(content=task_prompt, source="user")], cancellation_token=None
            )

            if response and response.chat_message:
                logger.info("快速周报总结生成成功")
                return response.chat_message.content
            else:
                logger.warning("快速周报总结生成失败")
                return None

        except Exception as e:
            logger.error(f"快速生成周报总结时发生错误: {e}")
            return None


# 全局实例
weekly_report_agent = WeeklyReportAgent()

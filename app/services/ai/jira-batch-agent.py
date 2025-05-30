import json
import os
import asyncio
from typing import List, Dict, Any, Optional

from autogen_core.models import ModelFamily
from autogen_core import CancellationToken
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination, ExternalTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger


class JiraBatchAgent:
    def __init__(self):
        # 初始化大语言模型客户端
        self.model_client = OpenAIChatCompletionClient(
            model=os.getenv("OPENAI_MODEL", "qwen-turbo-latest"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv(
                "OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,  # 优化JSON输出格式支持
                "family": ModelFamily.ANY,
                "structured_output": False,
            },
        )

        # 创建需求分析智能体 - 负责将需求转化为结构化的提单
        self.ticket_clarification_agent = AssistantAgent(
            name="requirements_analyst",
            model_client=self.model_client,
            system_message="""你是一位专业的需求分析师，负责将用户提出的需求转化为规范的研发提单。用户会提供一段描述，其中可能包含一个或多个需求。你需要将这些需求提取出来，并按照固定的模板进行结构化输出。

**处理流程：**

1.  **需求分析:** 仔细阅读用户输入，识别出所有的功能需求。注意，用户输入可能包含多个需求，需要逐一识别。如果无法提取到客户信息，默认客户为"新视窗"。
2.  **需求拆分:** 将每个需求拆分为独立的结构块。如果一个需求明显可以区分前端和后端工作，则将其拆分为两个结构块，分别对应前端和后端。拆分依据包括但不限于：
    * 明显的"前端"、"后端"字样。
    * 功能描述中涉及页面、交互（通常为前端）或接口、数据处理（通常为后端）。
    * 语句有明显的、语义分段、序号标记。
3.  **结构化输出:** 对于每个需求（或拆分后的前端/后端需求），按照以下模板生成提单内容：

    ```
    【客户名称】【项目/模块名称】需求标题 - <前端 | 后端> (如果需要拆分前后端，则添加此标签)
    【功能描述】:
    - 功能点1描述
    - 功能点2描述 (如果有多个功能点，逐条列出)
    【实现路径】：
    1. 实现步骤1 (参考文档链接如果有的话)
    2. 实现步骤2
    ... (根据需要添加更多步骤)
    ---
    ```
    * **客户名称:** 从用户输入中提取，如果未提供，则默认为"新视窗"。
    * **项目/模块名称:** 从用户输入中提取，例如"数据中台"、"APP"等。如果没有明确给出，可以根据需求内容推断一个合适的名称。推断时，优先使用常见的项目或模块名称，如"数据中台"、"APP"、"官网"等。
    * **需求标题:** 简洁概括需求内容。
    * **前端/后端:** 如果需求被拆分为前端和后端，则在此处添加相应的标签。
    * **功能描述:** 详细描述需求的功能点，使用短横线 (-) 分隔每个功能点。每个功能点应简洁明了，不宜过长。
    * **实现路径:** 列出实现该需求的具体步骤。如果用户提供了参考文档链接，将其包含在实现路径中。如果用户有具体前置内容要求，需要添加对应模版的<实现路径>中，例如："1. 确保已完成API接口对接。" 实现路径应包含足够的细节，以便研发人员理解，但避免过度冗余。
4.  **多需求处理:** 如果用户输入包含多个需求，重复步骤2和3，为每个需求生成一个独立的结构块。每个结构块之间用下划线 "---" 分隔，并确保有明确的换行。
5.  **检查与优化:** 确保每个需求都包含标题、功能点描述和实现路径。检查语言是否流畅、专业，并符合研发体系的要求。

**注意事项：**

* 严格遵守中文语境。
* 确保提单内容的专业性和准确性。
* 尽量保证标题都不相似，要看上去有明显的差异
* 输出纯文本内容，不包含任何XML标签。
* 每个需求结构块要有明确的换行、并且输出下划线标记进行分割。
""",
        )

        # 创建参数提取智能体 - 负责从结构化提单中提取JSON参数
        self.parameter_extractor_agent = AssistantAgent(
            name="parameter_extractor",
            model_client=self.model_client,
            system_message="""你是专业的结构化数据提取专家，负责将需求分析师处理的结构化文本转换为标准JSON格式。

你需要提取文本段落中的参数，包含一个名为 `jiraList` 的数组对象。

1. **提取 `jiraList` 参数** - `array[object]` - **必填** （所有单子的信息）
   - **对象结构：**
     - `title`: `string` - 必填。包含客户信息的总标题部分。
     - `customerName`: `string` - 必填。客户名称
     - `description`: `string` - 必填。包含【功能描述】和【实现路径】两部分的信息内容。

2. **富文本识别处理能力：**
   - 你具有富文本识别处理提取的能力。当原始文本中出现富文本渲染的链接（例如 Markdown 链接 `[文本](链接)` 或其他类似的富文本语法）时，请务必完整地识别并提取到 `description` 属性中。
   - 如果遇到无法完全解析的富文本语法，请在提取的字符串中使用明确的标记（例如 `<LINK: 原始链接内容>` 或 `<RICH_TEXT: 原始语法>`）来表达其存在，确保没有信息丢失。

### 文本分割规则：
- 每个独立的数据对象通常由 `---` 分隔。
- `title` 是紧随分隔符后的第一行内容，通常以 `【` 开头并以 `】` 结尾。
- `description` 包含 `【功能描述】` 和 `【实现路径】` 两部分的内容，直到下一个 `---` 分隔符或者文本结束。
- `customerName`: `string` - 必填。客户名称 （运用自然语言处理技术，准确判断并提取客户名、自动忽略非客户名称的干扰信息、客户名称要尽可能准确、精炼，最好去除地区名称或者性质描述。提取客户名称可以适当的简化，比如：江西乐奥==>乐奥、乐奥物业===》乐奥、乐奥集团==>乐奥）

### 注意和要求规范：
- **完整性：** 提取的内容必须与接收到的原始文本内容完全保持一致，不能缺失任何信息，也不能自由发挥或进行总结。
- **精确性：** 严格按照定义的字段和结构输出数据对象。
- **输出格式：** 仅输出提取到的 JSON 格式数据对象，不包含任何额外的解释或说明。
- **任务完成标记：** 当你完成JSON提取后，请以"JSON_DONE"结束你的回答，这样我们知道任务已完成。
""",
        )

        # 创建一个JSON验证智能体 - 确保输出的JSON是有效的
        self.json_validator_agent = AssistantAgent(
            name="json_validator",
            model_client=self.model_client,
            system_message="""
你是一位专业的JSON验证专家。你的职责是验证参数提取器生成的JSON是否有效，并确保它符合以下标准：

1. 语法正确，没有JSON解析错误
2. 包含所有必需的字段：jiraList数组，每个元素都有title、customerName和description
3. 没有额外的文本、解释或注释

如果JSON有效，请回复"VALID_JSON"，否则请修复JSON并以"FIXED_JSON"开头，然后是修复后的JSON。
""",
        )

        # 创建Team终止条件 - 当消息中包含"VALID_JSON"时停止
        self.termination_condition = TextMentionTermination("VALID_JSON")

        # 创建团队 - 使用RoundRobinGroupChat模式
        self.team = RoundRobinGroupChat(
            participants=[
                self.ticket_clarification_agent,
                self.parameter_extractor_agent,
                self.json_validator_agent,
            ],
            termination_condition=self.termination_condition,
        )

    def _extract_json_from_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """尝试从文本中提取JSON数组。"""
        try:
            json_start = text.find("[")
            json_end = text.rfind("]")
            if json_start != -1 and json_end != -1 and json_start < json_end:
                json_str = text[json_start : json_end + 1]
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, list):
                    return parsed_json
        except json.JSONDecodeError:
            logger.warning(f"Error decoding JSON from text: {text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during JSON extraction: {e}")
        return None

    async def process_message(self, user_message: str) -> List[Dict[str, Any]]:
        """使用Team模式处理用户输入，返回JSON数组"""
        # 重置团队状态，确保每次处理新消息时都是干净的状态
        await self.team.reset()

        # 使用 run 方法运行团队，传入用户消息作为任务
        logger.info(f"开始处理用户消息: {user_message}")
        logger.info("启动智能体团队处理...")

        # 使用 Console 进行直观展示团队交互过程
        # Console 可以将所有的消息和状态变化以可读性更高的格式展示出来
        logger.info("\n===== 团队交互过程开始 =====\n")
        result = await Console(self.team.run_stream(task=user_message))
        logger.info("\n===== 团队交互过程结束 =====\n")

        # 使用 run_stream 方法流式处理并记录中间过程
        # result = None
        # async for message in self.team.run_stream(task=user_message):
        #     if isinstance(message, TaskResult):
        #         # 最终结果
        #         result = message
        #         logger.info(f"团队处理完成，终止原因: {result.stop_reason}")
        #     else:
        #         # 中间消息，记录到日志
        #         if hasattr(message, "source") and hasattr(message, "content"):
        #             logger.debug(f"[{message.source}] {message.content[:100]}...")

        # 记录处理完成的状态
        logger.info(f"团队处理完成，终止原因: {result.stop_reason if result else 'Unknown'}")

        # 如果没有获得结果，返回空列表
        if not result:
            logger.error("团队处理失败，未返回有效结果")
            return []

        # 从最后一个验证器的消息中提取JSON
        for message in reversed(result.messages):
            if message.source == "json_validator" and "VALID_JSON" in message.content:
                # 找到前一条来自parameter_extractor的消息
                for prev_message in reversed(result.messages):
                    if prev_message.source == "parameter_extractor":
                        json_output_text = prev_message.content
                        parsed_json = self._extract_json_from_text(json_output_text)
                        if parsed_json:
                            logger.info(f"成功提取JSON，包含 {len(parsed_json)} 个项目")
                            return parsed_json

        # 如果无法找到有效的JSON，尝试从所有消息中提取
        for message in reversed(result.messages):
            if message.source == "parameter_extractor":
                json_output_text = message.content
                parsed_json = self._extract_json_from_text(json_output_text)
                if parsed_json:
                    logger.info(f"从参数提取器消息中提取JSON，包含 {len(parsed_json)} 个项目")
                    return parsed_json

        logger.error("无法从团队处理结果中提取有效JSON")
        return []


# --- 使用示例 ---
async def main():
    # 配置环境变量
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY 环境变量未设置")
        return

    # 初始化 JiraBatchAgent
    jira_agent_system = JiraBatchAgent()

    # 示例用户输入
    user_inputs = [
        "新力物业需要在系统中添加一个新功能，包括用户登录和数据同步，标题需要包含【数据中台】、这个是参考文档链接：https://docs.qq.com/sheet/DVlFwTGhRZE9tY2hz?no_promotion=1&tab=b1fd5q&nlc=1",
        "要求在APP中添加社交分享功能和消息推送。",
        "做一个官网，需要展示公司介绍、产品列表、联系我们三个页面。",
    ]

    for i, user_input in enumerate(user_inputs):
        result = await jira_agent_system.process_message(user_input)
        if result:
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            logger.error(f"输入 {i+1} 无结果")


if __name__ == "__main__":
    # 对于Windows平台，如果遇到asyncio问题，可能需要以下设置：
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

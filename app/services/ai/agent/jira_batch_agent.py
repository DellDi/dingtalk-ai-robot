import json
import os
import re
import asyncio
from typing import List, Dict, Any, Optional, TypedDict
from loguru import logger

from autogen_core import CancellationToken
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.conditions import TextMentionTermination, ExternalTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console

from app.db_utils import get_jira_account, save_jira_account
from app.services.ai.tools.jira_bulk_creator import JiraTicketCreator
from app.services.ai.client.openai_client import get_openai_client


# ---- TypedDict for input payload ---- #

class JiraInput(TypedDict):
    text: str
    sender_id: str
    conversation_id: str


class JiraAccountAgent:
    JIRA_ACCOUNT_REGEX = r"用户名[:：]\s*(\S+)\s*密码[:：]\s*(\S+)"

    def __init__(self):
        pass

    async def extract_and_save_account(self, user_id: str, text: str) -> str:
        user_info = get_jira_account(user_id)
        if user_info:
            return None  # 已有账号，直接返回None代表无需处理
        match = re.search(self.JIRA_ACCOUNT_REGEX, text)
        if match:
            username, password = match.groups()
            save_jira_account(user_id, username, password)
            return "账号保存成功，请重新输入提单内容。"
        creds = await self.handle_agent_params(text)
        if creds and isinstance(json.loads(creds), dict) and "username" in json.loads(creds) and "password" in json.loads(creds):
            user_info = json.loads(creds)
            username, password = user_info["username"], user_info["password"]
            save_jira_account(user_id, username, password)
            return "账号保存成功，请重新输入提单内容。"
        return "请输入你的**JIRA账号信息**（格式如下）：\n **配置jira信息**\n**用户名**: `your_jira_username`\n**密码**: `your_jira_password`"

    async def handle_agent_params(self, text: str) -> Optional[Dict[str, Any]]:
        """
        通过大模型参数提取- JIRA账号信息、JIRA密码
        出参格式：
        {
            "username": "jira_username",
            "password": "jira_password"
        }
        """
        model_client = get_openai_client(temperature=0)

        params_agent = AssistantAgent(
            name="parameter_extractor_account",
            model_client=model_client,
            system_message="""你是一位专业的参数提取专家，用户的输入中可能包含
                1. JIRA账号信息 - 用户名
                2. JIRA密码 - 用户密码
            请提取出上述信息，并以JSON格式返回，如果没有对应的账号密码信息，请提示用户重新输入。

            提取失败的格式如下：
            请输入你的**JIRA账号信息**（格式如下）：
            **用户名**: `your_jira_username`
            **密码**: `your_jira_password`

            提取成功输出json格式为：
            {
                "username": "xxx",
                "password": "xxx"
            }
            """,
        )

        messages = [TextMessage(content=text, source="user")]
        chat_res = await params_agent.on_messages(messages, CancellationToken())
        logger.info(f"JIRA账号：参数提取智能体响应: {chat_res}")
        return self._extract_last_response(chat_res)

    def _extract_last_response(self, chat_res: Response): # Adjusted type hint
        """
        提取最后一个消息的响应
        """
        last_message = chat_res.chat_message
        logger.info(f"最后一个消息: {last_message}")
        # Ensure last_message is TextMessage and has content
        if isinstance(last_message, TextMessage) and hasattr(last_message, 'content') and last_message.content:
            try:
                # Attempt to load JSON, ensure content is a string
                content_str = last_message.content
                if not isinstance(content_str, str): # pragma: no cover
                    # This case might occur if content is unexpectedly not a string
                    logger.warning(f"Last message content is not a string: {content_str}")
                    return None
                return json.loads(content_str)
            except json.JSONDecodeError: # pragma: no cover
                logger.warning(f"Error decoding JSON from text: {last_message.content}")
            except Exception as e: # pragma: no cover
                logger.error(f"An unexpected error occurred during JSON extraction: {e}")
        return None


class JiraBatchAgent:
    def __init__(self):
        # 初始化大语言模型客户端
        self.model_client = get_openai_client()
        # 封装账号提取智能体
        self.account_agent = JiraAccountAgent()

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
            name="parameter_extractor_tickets", # Renamed for clarity
            model_client=self.model_client,
            system_message="""你是专业的结构化数据提取专家，负责将需求分析师处理的结构化文本转换为标准JSON格式。

你需要提取文本段落中的参数，包含一个名为 `jiraList` 的数组对象。

1. **提取 `jiraList` 参数** - `array[object]` - **必填** （所有单子的信息）
   - **对象结构：**
     - `title`: `string` - 必填。包含客户信息的总标题部分。
     - `customerName`: `string` - 必填。客户名称
     - `description`: `string` - 必填。包含【功能描述】和【实现路径】两部分的信息内容，要包含换行符。

2. **富文本识别处理能力：**
   - 你具有富文本识别处理提取的能力。当原始文本中出现富文本渲染的链接（例如 Markdown 链接 `[文本](链接)` 或其他类似的富文本语法）时，请务必完整地识别并提取到 `description` 属性中。
   - 如果遇到无法完全解析的富文本语法，请在提取的字符串中使用明确的标记（例如 `<LINK: 原始链接内容>` 或 `<RICH_TEXT: 原始语法>`）来表达其存在，确保没有信息丢失。

### 文本分割规则：
- 每个独立的数据对象通常由 `---` 分隔。
- `title` 是紧随分隔符后的第一行内容，通常以 `【` 开头并以 `】` 结尾。
- `description` 包含 `【功能描述】` 和 `【实现路径】` 两部分的内容，要包含换行符，直到下一个 `---` 分隔符或者文本结束。
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

    async def process(self, input: JiraInput) -> str:
        logger.info(f"开始为用户 {input.get('sender_id')} 处理Jira批量代理请求: {input.get('text')[:100]}...")
        text = input.get("text")
        user_id = input.get("sender_id")

        # 1. 账号信息智能体优先处理
        account_result = await self.account_agent.extract_and_save_account(user_id, text)
        if account_result:  # 有提示语，说明账号未补全或刚保存成功让用户重试，直接返回提示
            logger.info(f"用户 {user_id} 账号处理结果: {account_result}")
            return account_result

        # 2. 账号已齐全，进入提单分析主流程
        logger.info(f"用户 {user_id} 账号已存在或已处理，开始解析提单内容...")
        parsed_ticket_data_list = await self.process_message(text)

        if not parsed_ticket_data_list:
            logger.warning(f"用户 {user_id} 的输入未能通过AI解析出任何有效的工单信息。原始输入: {text}")
            return "抱歉，我未能从您的输入中准确解析出需要创建的工单信息。请尝试调整您的描述或检查格式。"

        # 3. 获取Jira执行凭据 (用户名和密码从数据库获取) (variable) user_jira_account: Tuple[str, str] | None

        user_jira_account = get_jira_account(user_id)
        jira_user, jira_password = user_jira_account

        if not user_jira_account or not jira_user or not jira_password:
            logger.error(f"用户 {user_id} 在数据库中未找到有效的Jira账号凭据。")
            return "错误：未能获取到您已保存的Jira账号信息，请确认您已正确设置Jira账号。"

        # 4. 设置批量创建所需的固定参数
        assignee = jira_user  # 经办人与Jira用户名一致
        auth_token = "zd-nb-19950428" # 固定认证令牌 (JiraTicketCreator内部会处理Bearer)
        labels = "智慧数据,快捷工单"    # 固定标签

        logger.info(f"用户 {user_id} 的Jira凭据和固定参数已准备就绪。准备为 {len(parsed_ticket_data_list)} 个工单进行批量创建。")

        # 5. 执行批量创建
        ticket_creator = None # Initialize to ensure it's defined for finally block
        try:
            ticket_creator = JiraTicketCreator(
                jira_user=jira_user,
                jira_password=jira_password,
                assignee=assignee,
                labels=labels,
                auth_token=auth_token
            )
            creation_results = await ticket_creator.bulk_create_tickets(parsed_ticket_data_list)
            markdown_report = ticket_creator.format_results_to_markdown(creation_results)

            logger.info(f"用户 {user_id} 的批量工单创建流程处理完毕，已生成Markdown报告。")
            return markdown_report
        except Exception as e:
            logger.error(f"为用户 {user_id} 执行批量创建Jira工单或生成报告时发生意外错误: {e}", exc_info=True)
            return f"抱歉，处理您的批量工单请求时遇到了内部错误。请稍后重试或联系技术支持。错误参考: {e}"
        finally:
            if ticket_creator and ticket_creator.client:
                await ticket_creator.client.aclose() # 确保客户端总是被关闭
                logger.info(f"用户 {user_id} 的JiraTicketCreator客户端已关闭。")

    def _extract_json_from_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """尝试从文本中提取JSON数组。"""
        try:
            # 尝试找到最外层的JSON结构，应该是jiraList的列表
            # 更健壮的方式可能是查找 "jiraList": [...]
            # 目前假设相关的JSON列表是找到的第一个顶层列表

            # 处理JSON可能嵌入在其他文本或markdown代码块中的情况
            match = re.search(r'```json\s*([\s\S]*?)\s*```', text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                # Fallback: find first '[' and last ']'
                json_start = text.find("[")
                json_end = text.rfind("]")
                if json_start != -1 and json_end != -1 and json_start < json_end:
                    json_str = text[json_start : json_end + 1]
                else: # pragma: no cover
                    logger.warning(f"Could not find JSON array structure in text: {text[:200]}...")
                    return None

            parsed_data = json.loads(json_str)

            # The prompt for parameter_extractor_agent asks for a JSON with a "jiraList" key.
            if isinstance(parsed_data, dict) and "jiraList" in parsed_data:
                jira_list = parsed_data["jiraList"]
                if isinstance(jira_list, list):
                    # Validate structure of items in jira_list (optional, but good practice)
                    for item in jira_list:
                        if not (isinstance(item, dict) and "title" in item and "customerName" in item and "description" in item):
                            logger.warning(f"Invalid item structure in jiraList: {item}")
                            return None # Or handle more gracefully
                    return jira_list
                else: # pragma: no cover
                    logger.warning(f"发现jiraList密钥，但其值不是一个列表： {type(jira_list)}")
                    return None
            elif isinstance(parsed_data, list): # pragma: no cover
                # 如果智能体直接返回列表而不是 {"jiraList": [...]} 格式时的回退处理
                logger.warning("解析的JSON提取是一个清单，但期望与 'jiraList' 的键。试图直接使用列表。")
                return parsed_data # This might happen if the LLM doesn't follow instructions perfectly
            else: # pragma: no cover
                logger.warning(f"解析的JSON既不是包含 'jiraList' 键的对象，也不是直接的列表: {text[:200]}...")
                return None

        except json.JSONDecodeError: # pragma: no cover
            logger.warning(f"Error decoding JSON from text: {text[:200]}...")
        except Exception as e: # pragma: no cover
            logger.error(f"An unexpected error occurred during JSON extraction: {e}")
        return None

    async def process_message(self, user_message: str) -> List[Dict[str, Any]]:
        """使用Team模式处理用户输入，返回包含工单数据的JSON数组"""
        await self.team.reset()

        logger.info(f"JiraBatchAgent: 开始通过智能体团队处理用户消息: {user_message[:100]}...")

        # The task for the team is the user's raw text input
        task_result_message = await self.team.run(task=user_message)

        logger.info(f"JiraBatchAgent: 团队处理完成。停止原因: {task_result_message.stop_reason if task_result_message else '未知'}")

        if not task_result_message or not hasattr(task_result_message, "messages") or not task_result_message.messages:
            logger.error("JiraBatchAgent: 团队处理失败或未返回任何消息。")
            return []

        # 验证器智能体是最后一个。它的倒数第二条消息(N-1)应该包含JSON内容。
        # 验证器的最后一条消息(N)应该是"VALID_JSON"或"FIXED_JSON..."这样的状态标记
        final_validator_status_message = task_result_message.messages[-1]

        if not isinstance(final_validator_status_message, TextMessage) or not final_validator_status_message.content:
            logger.error("JiraBatchAgent: 最终验证状态消息无效或为空。")
            return []

        logger.debug(f"JiraBatchAgent: 验证器状态消息内容: {final_validator_status_message.content[:100]}")

        # 实际的JSON内容应该在验证器最终状态消息的前一条消息中
        # 这条消息来自参数提取智能体(parameter_extractor_agent)，或者如果JSON被修复过，则来自JSON验证智能体(json_validator_agent)
        if len(task_result_message.messages) < 2: # pragma: no cover
            logger.error("JiraBatchAgent: 消息列表不足，无法提取JSON内容。")
            return []

        json_content_message = task_result_message.messages[-2] # Message from parameter_extractor or fixed by validator

        if not isinstance(json_content_message, TextMessage) or not json_content_message.content:
            logger.error("JiraBatchAgent: JSON内容消息无效或为空。")
            return []

        logger.debug(f"JiraBatchAgent: 尝试从以下内容提取JSON: {json_content_message.content[:200]}")

        if "VALID_JSON" in final_validator_status_message.content or "FIXED_JSON" in final_validator_status_message.content:
            parsed_json_list = self._extract_json_from_text(json_content_message.content)
            if parsed_json_list:
                logger.info(
                    f"JiraBatchAgent: 成功从团队输出中提取JSON，包含 {len(parsed_json_list)} 个工单项目。"
                )
                # Log model usage if available from the TaskResult
                if hasattr(task_result_message, 'models_usage') and task_result_message.models_usage: # pragma: no cover
                    logger.info(f"JiraBatchAgent: 模型调用消耗: {task_result_message.models_usage}")
                return parsed_json_list
            else: # pragma: no cover
                logger.warning("JiraBatchAgent: 验证器指示JSON有效/已修复，但未能从其前一条消息中提取结构化JSON列表。")
        else: # pragma: no cover
            logger.warning(f"JiraBatchAgent: JSON验证未通过或未收到预期的验证状态。验证器消息: {final_validator_status_message.content}")

        logger.error("JiraBatchAgent: 无法从团队处理结果中提取有效的JSON列表。")
        return []


# --- 使用示例 ---
async def main(): # pragma: no cover
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
        # Test with account info
        "用户名: test_user 密码: test_password \n 请帮我处理以下工单：客户A需要一个新的报表功能，客户B需要修复登录bug。",
    ]

    mock_sender_id = "test_sender_123"
    mock_conversation_id = "conv_456"

    # Mock get_jira_account and save_jira_account for main example if needed
    # For this example, we assume they work or we test the flow where account exists or is newly saved.

    for i, user_input_text in enumerate(user_inputs):
        logger.info(f"\n--- 处理输入 {i+1}: {user_input_text[:50]}... ---")

        # Simulate account already exists for some inputs to test the main flow
        if i % 2 == 0 and "用户名" not in user_input_text : # For even inputs without credentials, assume account exists
            if not get_jira_account(mock_sender_id): # if not already mocked by a previous cred input
                 save_jira_account(mock_sender_id, "mock_user", "mock_pass")
                 logger.info(f"Mock: 用户 {mock_sender_id} 账号已预设。")
        elif "用户名" not in user_input_text: # For odd inputs, clear account to test extraction/prompt
             if get_jira_account(mock_sender_id):
                # This is tricky as db_utils is not easily mockable here.
                # For a real test, you'd use a test DB or mock db_utils.
                logger.info(f"Mock: 清除用户 {mock_sender_id} 的Jira账号信息以测试提取流程 (假定操作)。")


        input_payload = {"text": user_input_text, "sender_id": mock_sender_id, "conversation_id": mock_conversation_id}
        result_dict = await jira_agent_system.process(input_payload)

        logger.info(f"输入 {i+1} 的最终处理结果:")
        if isinstance(result_dict, dict) and "content" in result_dict:
            logger.info(f"\n{result_dict['content']}\n")
        else: # pragma: no cover
            logger.warning(f"处理结果格式非预期: {result_dict}")


if __name__ == "__main__": # pragma: no cover
    # 对于Windows平台，如果遇到asyncio问题，可能需要以下设置：
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

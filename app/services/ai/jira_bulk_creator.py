import httpx
import asyncio
import json
from typing import List, Dict, Any, Optional
from loguru import logger
import os # 确保 os 模块已导入，以便使用 getenv

# Jira API 相关配置信息 - 后续可以考虑通过更灵活的配置方式管理
JIRA_API_URL = "https://dify.yswg360.com/fastify/dify/create-jira" # 创建Jira工单的API接口地址
JIRA_API_POINT = "app.create_jira_tool" # Jira API 功能点

class JiraTicketCreator:
    def __init__(self, jira_user: str, jira_password: str, assignee: str, labels: str, auth_token: str):
        self.jira_user = jira_user
        self.jira_password = jira_password
        self.assignee = assignee
        self.labels = labels
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(timeout=30.0) # 为网络请求增加超时时间

    async def create_single_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用提供的工单数据创建单个Jira工单。
        `ticket_data` 应包含 'title', 'customerName', 和 'description'。
        """
        title = ticket_data.get("title", "未提供标题")
        description = ticket_data.get("description", "未提供描述")
        customer_name = ticket_data.get("customerName", "杭州新视窗") # 如果未提供，则使用默认值

        payload = {
            "point": JIRA_API_POINT,
            "title": title,
            "description": description,
            "labels": self.labels,
            "assignee": self.assignee,
            "jiraUser": self.jira_user,
            "jiraPassword": self.jira_password, # 注意：以这种方式发送密码存在安全风险。
            "customerName": customer_name,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}", # 假设使用 Bearer token 授权
        }

        logger.info(f"尝试创建Jira工单: {title}")
        logger.debug(f"请求体: {json.dumps(payload, ensure_ascii=False)}") # 记录请求体用于调试，ensure_ascii=False 以正确显示中文

        try:
            response = await self.client.post(JIRA_API_URL, json=payload, headers=headers)
            response.raise_for_status()  # 对错误的响应 (4xx 或 5xx) 抛出 HTTPStatusError

            response_data = response.json()
            logger.info(f"成功创建工单: {title}, ID: {response_data.get('issueId')}, Key: {response_data.get('issueKey')}")
            return {
                "success": True,
                "title": title,
                "issueKey": response_data.get("issueKey"),
                "issueId": response_data.get("issueId"),
                "issueUrl": response_data.get("issueUrl"),
                "response": response_data,
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"创建工单 '{title}' 时发生HTTP错误: {e.response.status_code} - {e.response.text}")
            return {"success": False, "title": title, "error": f"HTTP错误: {e.response.status_code}", "details": e.response.text}
        except httpx.RequestError as e:
            logger.error(f"创建工单 '{title}' 时发生请求错误: {e}")
            return {"success": False, "title": title, "error": "请求错误", "details": str(e)}
        except json.JSONDecodeError as e: # 特别捕获JSON解码错误
            response_text = e.response.text if hasattr(e, 'response') else 'N/A'
            logger.error(f"解码工单 '{title}' 的JSON响应失败: {e}。响应文本: {response_text}")
            return {"success": False, "title": title, "error": "JSON解码错误", "details": str(e), "responseText": response_text}
        except Exception as e:
            logger.error(f"创建工单 '{title}' 时发生意外错误: {e}")
            return {"success": False, "title": title, "error": "意外错误", "details": str(e)}

    async def bulk_create_tickets(self, tickets_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        并发批量创建多个Jira工单。
        """
        if not tickets_data:
            logger.info("未提供用于批量创建的工单数据。")
            return []

        logger.info(f"开始批量创建 {len(tickets_data)} 个工单。")

        tasks = [self.create_single_ticket(ticket) for ticket in tickets_data]
        # return_exceptions=True 用于处理单个任务的失败情况
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            original_title = tickets_data[i].get("title", f"工单 {i+1}")
            # 此处捕获从 create_single_ticket 抛出的异常或 asyncio 本身的异常
            if isinstance(result, Exception):
                logger.error(f"批量创建 '{original_title}' 过程中发生异常: {result}")
                # 为 gather 捕获的异常确保一致的错误结构
                processed_results.append({"success": False, "title": original_title, "error": "gather执行期间发生未处理异常", "details": str(result)})
            else:
                # 这个 'result' 是 create_single_ticket 返回的字典
                processed_results.append(result)

        logger.info(f"批量创建过程完成。共处理 {len(processed_results)} 个结果。")
        return processed_results

    def format_results_to_markdown(self, results: List[Dict[str, Any]]) -> str:
        """
        将批量创建的结果格式化为Markdown字符串。
        """
        logger.info(f"正在将 {len(results)} 个结果格式化为Markdown。")
        report_lines = ["## Jira 批量创建报告"]

        successful_tickets = [r for r in results if r.get("success")]
        failed_tickets = [r for r in results if not r.get("success")]

        if successful_tickets:
            report_lines.append("\n### ✅ 成功创建的工单:")
            for ticket in successful_tickets:
                issue_key = ticket.get('issueKey', 'N/A')
                issue_url = ticket.get('issueUrl', '#')
                report_lines.append(f"- **{ticket.get('title', 'N/A')}**: [{issue_key}]({issue_url})")

        if failed_tickets:
            report_lines.append("\n### ❌ 创建失败的工单:")
            for ticket in failed_tickets:
                error_details = ticket.get('details', '未提供详情')
                # 避免在摘要中显示过长的详情，完整详情已在其他地方记录
                if len(error_details) > 200: # 稍微增加了长度限制
                    error_details = error_details[:200] + "..."
                report_lines.append(f"- **{ticket.get('title', 'N/A')}**: {ticket.get('error', '未知错误')} (详情: {error_details})")

        if not results:
            report_lines.append("\n未处理任何工单或无可用结果。")

        return "\n".join(report_lines)

async def main():
    logger.info("Jira批量创建脚本已启动。")

    sample_tickets_data = [
        {"title": "【测试客户】修复前端登录错误", "customerName": "测试客户", "description": "用户在密码重置后无法登录。步骤：1. 验证重置令牌。2. 检查会话管理。"},
        {"title": "【另一客户】实现后端新功能X", "customerName": "另一客户", "description": "为功能X开发API端点。路径: /api/featurex, /api/featurex/{id}"},
        {"title": "缺失描述测试", "customerName": "测试公司"}, # 测试用例：描述缺失
        {"title": "【好公司】更新UI元素", "customerName": "好公司", "description": "更新仪表盘的外观和体验。"}
    ]

    # 重要提示：在实际测试时，请替换为真实的凭据和参数
    # 从环境变量加载，带有回退值
    jira_user = os.getenv("JIRA_USER", "testuser_fallback_cn")
    jira_password = os.getenv("JIRA_PASSWORD", "testpassword_fallback_cn")
    assignee = os.getenv("JIRA_ASSIGNEE", "testassignee_fallback_cn")
    labels = os.getenv("JIRA_LABELS", "BulkTestCN,AutoGenFallbackCN")
    auth_token = os.getenv("JIRA_AUTH_TOKEN", "YOUR_AUTH_TOKEN_HERE")

    if auth_token == "YOUR_AUTH_TOKEN_HERE" or not auth_token:
        logger.warning("正在使用占位符或缺失 JIRA_AUTH_TOKEN。真实的API调用可能会失败或未经授权。")
        logger.warning("请设置 JIRA_AUTH_TOKEN 环境变量以进行实际的Jira交互。")
        # 脚本将继续执行，但没有有效令牌的API调用预计会失败。
        # 对于没有实时Jira的本地测试，这是可接受的。
        # 对于针对实时系统的测试，此令牌必须有效。
        # 考虑使用模拟服务器进行更稳健的本地测试。

    creator = JiraTicketCreator(
        jira_user=jira_user,
        jira_password=jira_password,
        assignee=assignee,
        labels=labels,
        auth_token=auth_token
    )

    logger.info(f"模拟批量创建 {len(sample_tickets_data)} 个工单。如果JIRA_AUTH_TOKEN无效或指向无效的端点，这些操作将会失败。")
    creation_results = await creator.bulk_create_tickets(sample_tickets_data)

    markdown_report = creator.format_results_to_markdown(creation_results)

    logger.info("\n--- 生成的Markdown报告 ---")
    print(markdown_report) # 将Markdown报告打印到控制台
    logger.info("--- Markdown报告结束 ---")

    await creator.client.aclose() # 确保 httpx 客户端已关闭
    logger.info("Jira批量创建脚本已完成。")

if __name__ == "__main__":
    # 配置 Loguru 以获得更好的控制台输出
    logger.remove() # 移除默认的处理器（如果有）
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO" # 设置默认日志级别
    )

    # 使用环境变量运行的说明：
    # export JIRA_USER="你的Jira用户名"
    # export JIRA_PASSWORD="你的Jira密码"
    # export JIRA_ASSIGNEE="受理人用户名"
    # export JIRA_LABELS="SaaS,自动生成"
    # export JIRA_AUTH_TOKEN="你的真实API令牌"
    #
    # 然后运行: python app/services/ai/jira_bulk_creator.py
    asyncio.run(main())

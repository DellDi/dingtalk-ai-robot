#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH工具模块，支持自由模式和一键升级模式
"""

import re
import asyncio
from typing import Dict, Any, List
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from loguru import logger
from pydantic import json_schema

from app.services.ai.client.openai_client import get_openai_client
from app.services.ssh.client import SSHClient, SSHManager
from app.core.config import settings


async def process_ssh_request(
    request_text: str,
    host: str,
    mode: str = "free",  # free 或 upgrade
    sender_id: str = "",
    conversation_id: str = "",
) -> str:
    """
    处理SSH请求

    参数:
    - request_text: 用户请求文本
    - host: 目标主机
    - mode: 操作模式 (free/upgrade)
    - sender_id: 发送者ID
    - conversation_id: 会话ID

    返回:
    - 格式化后的执行结果
    """
    try:
        if mode == "upgrade":
            return await _process_upgrade_mode(host)
        else:
            return await _process_free_mode(request_text, host)
    except Exception as e:
        logger.error(f"SSH处理失败: {e}")
        return f"❌ SSH操作失败: {str(e)}"


async def _process_free_mode(request_text: str, host: str) -> str:
    """自由模式处理"""
    # 使用智能命令处理团队来处理请求
    return await _process_with_command_team(request_text, host)


async def _process_with_command_team(request_text: str, host: str) -> str:
    """使用两阶段执行模式处理SSH命令请求，避免重复执行"""
    try:
        logger.info(f"[SSH-COMMAND-TEAM] 开始处理请求: {request_text}")
        
        # 创建模型客户端
        client = get_openai_client(model_info={"json_output": False})
        
        # 第一阶段：命令规划阶段 - 使用多角色思考模式整合原有的命令审查和矫正功能
        command_planner = AssistantAgent(
            name="CommandPlanner",
            system_message=f"""你是一个Linux命令规划专家，负责根据用户请求生成最合适的命令。你需要扮演三个角色：命令生成器、安全审查官和命令优化师，按顺序完成命令处理流程。

【角色1：命令生成器】
首先，分析用户请求，生成能满足需求的Linux命令。确保：
- 只生成可直接在远程主机上执行的命令
- 不包含ssh连接前缀
- 如需sudo权限，明确添加sudo
- 优先使用标准Linux命令

【角色2：安全审查官】
然后，审查生成的命令是否存在以下安全风险：
- 交互式命令（需要用户输入或持续交互）
- 长时间运行或可能挂起的命令
- 等待用户确认的命令
- 进入特殊模式的命令（如编辑器、分页器）
- 潜在的危险操作（删除系统文件、修改关键配置等）
- 资源密集型操作（可能导致服务器负载过高）

【角色3：命令优化师】
最后，如果发现安全问题，优化命令使其安全可执行：
- 交互式查看 → 一次性输出（如 top -bn1 代替 top）
- 持续监控 → 快照查看（如 ps aux | grep <进程> 代替 watch）
- 编辑操作 → 查看操作（如 cat 代替 vim/nano）
- 分页显示 → 直接输出（如 cat 代替 less/more）
- 添加适当的限制参数（如 head、tail、timeout）
- 对于耗时操作，添加资源限制（如 nice、ionice）

请按照以下结构返回JSON格式的分析结果：
```json
{{
  "user_intent": "用户意图的详细描述",
  "initial_command": "初始生成的命令",
  "safety_analysis": "安全分析结果，详细说明潜在问题",
  "command": "最终优化后的安全命令",
  "reasoning": "命令选择和优化的详细理由",
  "estimated_runtime": "预估运行时间（秒）",
  "potential_issues": ["可能存在的问题列表"]
}}
```

重要提示：
1. 对于主机 {host} 上的命令，必须确保命令不会挂起或需要用户交互
2. 对于可能长时间运行的命令，添加适当的限制（如 timeout 命令）
3. 对于需要查看大量输出的命令，添加适当的过滤（如 head、grep）
4. 对于系统状态监控，优先使用一次性快照而非持续监控
5. 始终提供详细的安全分析，即使命令看起来是安全的
""",
            model_client=client,
        )
        
        # 第一阶段：获取命令规划结果
        planning_result = await planning_phase(command_planner, request_text)
        if not planning_result:
            return "❌ 命令规划失败，无法生成有效命令"
            
        # 提取计划好的命令
        try:
            import json
            # 解析JSON结果
            command_data = json.loads(planning_result)
            command_to_execute = command_data.get("command", "")
            if not command_to_execute:
                return "❌ 命令规划结果无效，未找到可执行命令"
                
            logger.info(f"[SSH-COMMAND-TEAM] 规划阶段生成命令: {command_to_execute}")
        except json.JSONDecodeError:
            # 如果JSON解析失败，尝试直接从文本中提取命令
            match = re.search(r'"command"\s*:\s*"([^"]+)"', planning_result)
            if match:
                command_to_execute = match.group(1)
                logger.info(f"[SSH-COMMAND-TEAM] 从文本提取命令: {command_to_execute}")
            else:
                return "❌ 无法从规划结果中提取命令"
        
        # 第二阶段：命令执行阶段 - 直接执行命令并返回结果
        logger.info(f"[SSH-COMMAND-TEAM] 执行命令: {command_to_execute}")
        timeout = await _smart_timeout_detection(command_to_execute)
        execution_result = await _execute_ssh_command(host, command_to_execute, timeout)
        
        return execution_result
        
    except Exception as e:
        logger.error(f"[SSH-COMMAND-TEAM] 处理异常: {e}")
        return f"❌ 命令处理异常: {str(e)}"


async def planning_phase(planner: AssistantAgent, request_text: str) -> str:
    """命令规划阶段，使用单个智能体生成并优化命令"""
    try:
        # 创建初始消息
        messages = [TextMessage(content=request_text, source="user")]
        
        # 设置超时时间，防止规划阶段耗时过长
        result = await asyncio.wait_for(planner.run(task=messages), timeout=30.0)
        
        # 从结果中提取最后一条消息的内容
        if result and hasattr(result, 'messages') and result.messages:
            # 获取最后一条消息
            last_message = result.messages[-1]
            if hasattr(last_message, 'content'):
                return last_message.content
        return ""
    except asyncio.TimeoutError:
        logger.warning("[SSH-COMMAND-TEAM] 命令规划阶段超时")
        return ""
    except Exception as e:
        logger.error(f"[SSH-COMMAND-TEAM] 命令规划异常: {e}")
        return ""
        
        # 这部分代码已被新的两阶段执行模式替代
        
        # 如果没有找到合适的结果，回退到简单逻辑
        logger.warning("[SSH-COMMAND-TEAM] 未找到有效的执行结果，回退到简单逻辑")
        return await _simple_fallback(request_text, host)
        
    except Exception as e:
        logger.error(f"[SSH-COMMAND-TEAM] 团队处理异常: {e}")
        return await _simple_fallback(request_text, host)


async def _smart_timeout_detection(command: str) -> int:
    """使用AI智能检测命令的合适超时时间"""
    try:
        client = get_openai_client(model_info={"json_output": False})
        timeout_agent = AssistantAgent(
            name="TimeoutAnalyzer",
            system_message="""你是一个命令执行时间分析专家。分析给定的Linux命令可能需要的执行时间。

分析维度：
1. 命令类型（系统查询、文件操作、网络操作、包管理等）
2. 可能的数据量
3. 系统资源需求
4. 网络依赖

超时建议：
- 快速查询命令（ls, ps, df等）：30-60秒
- 中等操作（服务重启、文件查找等）：120-180秒
- 长时间操作（下载、编译、大文件操作等）：300-600秒

只返回一个数字（秒数），不要任何解释。""",
            model_client=client,
        )
        
        messages = [TextMessage(content=f"分析命令执行时间: {command}", source="user")]
        result = await timeout_agent.run(task=messages)
        
        if result and result.messages:
            timeout_str = result.messages[-1].content.strip()
            try:
                timeout = int(timeout_str)
                return max(30, min(600, timeout))  # 限制在30-600秒之间
            except ValueError:
                pass
    except Exception as e:
        logger.warning(f"智能超时检测失败: {e}")
    
    # 默认超时
    return 60


async def _simple_fallback(request_text: str, host: str) -> str:
    """简化的回退处理逻辑"""
    # 直接使用原始的命令提取逻辑
    command = await _extract_command_intent(request_text)
    if not command:
        return "⚠️ 无法从您的请求中提取有效命令，请更明确地说明您想执行的操作"

    logger.info(f"[SSH-SIMPLE-FALLBACK] 处理命令: {command}")
    
    # 使用智能超时检测
    timeout = await _smart_timeout_detection(command)
    
    # 执行SSH命令
    return await _execute_ssh_command(host, command, timeout)


async def _execute_ssh_command(host: str, command: str, timeout: int = 60) -> str:
    """执行SSH命令"""
    client = SSHClient(host)
    connected = await client.connect()
    if not connected:
        return f"❌ 无法连接到主机 {host}"

    exit_code, stdout, stderr = await client.execute_command(command, timeout=timeout)
    client.close()

    # 格式化结果
    return _format_command_result(host, command, exit_code, stdout, stderr)


async def _process_upgrade_mode(host: str) -> str:
    """一键升级模式处理"""
    upgrade_commands = [
        "cd /opt/dify/docker",
        "cp docker-compose.yaml docker-compose.yaml.$(date +%s).bak",
        "git checkout main",
        "git pull origin main",
        "docker compose down",
        "tar -cvf volumes-$(date +%s).tgz volumes",
        "docker compose up -d",
    ]

    full_command = " && ".join(upgrade_commands)
    logger.info(f"[SSH-TOOL-DEBUG] 升级模式执行命令: {full_command}")
    
    # 升级操作需要更长的超时时间（10分钟）
    upgrade_timeout = 600
    logger.info(f"[SSH-TOOL-DEBUG] 升级模式超时设置: {upgrade_timeout}秒")
    
    client = SSHClient(host)
    connected = await client.connect()
    if not connected:
        return f"❌ 无法连接到主机 {host}"

    exit_code, stdout, stderr = await client.execute_command(full_command, timeout=upgrade_timeout)
    client.close()

    # 格式化升级结果
    result = f"## 🚀 Dify服务升级执行结果 ({host})\n"
    result += f"**执行的命令:**\n```bash\n{full_command}\n```\n"
    result += f"**超时设置:** {upgrade_timeout}秒\n"

    if exit_code == 0:
        result += "✅ 升级命令执行成功\n"
        result += f"**输出:**\n```\n{stdout}\n```"
    elif exit_code == -2:
        result += "⏰ 升级命令执行超时\n"
        result += f"**提示:** 升级可能需要更长时间，建议检查服务状态\n"
        result += f"**错误输出:**\n```\n{stderr}\n```"
    else:
        result += "❌ 升级命令执行失败\n"
        result += f"**错误代码:** {exit_code}\n"
        result += f"**错误输出:**\n```\n{stderr}\n```"

    return result


# 已删除硬编码的命令检测函数，改为使用AI智能体进行分析

async def _extract_command_intent(text: str) -> str:
    """使用AI智能体从用户文本生成合适的SSH命令"""

    prompt = f"""
    你是一个Linux系统管理员，需要根据用户请求生成合适的Linux命令。

    请遵循以下规则:
    1. 只返回可直接在远程主机上执行的Linux命令，不要包含ssh连接命令
    2. 不要包含ssh、ssh://等连接前缀，因为我们已经在SSH会话内部
    3. 确保命令安全，不要执行危险操作
    4. 优先使用标准Linux命令
    5. 如果需要sudo权限，请明确添加sudo

    生成的命令:
    """

    try:
        client = get_openai_client(model_info={"json_output": False})
        ssh_agent = AssistantAgent(
            name="ssh_agent",
            system_message=prompt,
            description="一个专门用于生成SSH命令的AI智能助手，你的回复必须是一个可执行的Linux命令，且不需要解释",
            model_client=client,
        )
        # response = await ssh_agent.generate_text(prompt, max_tokens=50)
        messages = [TextMessage(content=text, source="user")]
        chat_res = await ssh_agent.run(task=messages)
        logger.info(f"参数提取智能体响应: {chat_res}")
        if not chat_res:
            return "⚠️ 无法从您的请求中提取有效命令，请更明确地说明您想执行的操作"
        return chat_res.messages[-1].content.strip()  # 返回最后一条消息内容
    except Exception as e:
        logger.error(f"AI命令生成失败: {e}")
        return text.strip()  # 失败时返回原始文本


def _format_command_result(
    host: str, command: str, exit_code: int, stdout: str, stderr: str
) -> str:
    """格式化命令执行结果"""
    result = f"## 🖥️ 命令执行结果 ({host})\n"
    result += f"**执行的命令:**\n```bash\n{command}\n```\n"

    if exit_code == 0:
        result += "✅ 命令执行成功\n"
        if stdout:
            result += f"**输出:**\n```\n{stdout}\n```"
        else:
            result += "_(无输出)_"
    else:
        result += "❌ 命令执行失败\n"
        result += f"**错误代码:** {exit_code}\n"
        if stderr:
            result += f"**错误输出:**\n```\n{stderr}\n```"
        else:
            result += "_(无错误输出)_"

    return result

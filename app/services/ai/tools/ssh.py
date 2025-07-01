#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH工具模块，支持自由模式和一键升级模式
"""

import re
from typing import Dict, Any, List
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination

from loguru import logger
from pydantic import json_schema

from app.services.ai.openai_client import get_openai_client
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
    """使用RoundRobinGroupChat智能命令处理团队"""
    try:
        logger.info(f"[SSH-COMMAND-TEAM] 开始处理请求: {request_text}")
        
        # 创建模型客户端
        client = get_openai_client(model_info={"json_output": False})
        
        # 第一个智能体：命令生成器
        command_generator = AssistantAgent(
            name="CommandGenerator",
            system_message="""你是一个Linux命令生成专家。根据用户请求生成合适的Linux命令。

重要规则：
1. 只返回可直接在远程主机上执行的Linux命令，不要包含ssh连接命令
2. 不要包含ssh、ssh://等连接前缀，因为我们已经在SSH会话内部
3. 确保命令安全，不要执行危险操作
4. 优先使用标准Linux命令
5. 如果需要sudo权限，请明确添加sudo
6. 生成命令后，在末尾添加 NEXT_AGENT

正确示例：
uptime && free -h && df -h
NEXT_AGENT

错误示例（不要这样做）：
ssh user@host uptime
ssh://user@host/command
NEXT_AGENT""",
            model_client=client,
        )
        
        # 第二个智能体：命令安全分析师
        command_analyzer = AssistantAgent(
            name="CommandAnalyzer",
            system_message="""你是一个命令安全分析专家。分析上一个智能体生成的命令是否存在以下问题：

分析维度：
1. 是否为交互式命令（需要用户输入或持续交互）
2. 是否可能长时间运行或挂起
3. 是否会等待用户确认
4. 是否会进入特殊模式（如编辑器、分页器）

如果命令安全可执行，回复：
SAFE_COMMAND
NEXT_AGENT

如果发现问题，详细说明问题并回复：
PROBLEMATIC_COMMAND: [具体问题描述]
NEXT_AGENT""",
            model_client=client,
        )
        
        # 第三个智能体：命令优化器
        command_optimizer = AssistantAgent(
            name="CommandOptimizer",
            system_message="""你是一个命令优化专家。根据前面智能体的分析结果：

如果命令被标记为SAFE_COMMAND：
- 直接使用原命令
- 回复格式：[原命令]
EXECUTE_COMMAND

如果命令被标记为PROBLEMATIC_COMMAND：
- 分析用户的真实意图
- 提供功能等效但安全的替代命令
- 确保替代命令能达到相同目的但不会挂起

替代策略：
- 交互式查看 → 一次性输出
- 持续监控 → 快照查看
- 编辑操作 → 查看操作
- 分页显示 → 直接输出

回复格式：[优化后的安全命令]
EXECUTE_COMMAND""",
            model_client=client,
        )
        
        # 第四个智能体：命令执行器
        async def execute_command_tool(command: str) -> str:
            """执行SSH命令的工具函数"""
            logger.info(f"[SSH-COMMAND-TEAM] 执行命令: {command}")
            # 智能设置超时时间
            timeout = await _smart_timeout_detection(command.strip())
            return await _execute_ssh_command(host, command.strip(), timeout)
        
        command_executor = AssistantAgent(
            name="CommandExecutor",
            system_message=f"""你是一个命令执行专家。执行上一个智能体优化后的安全命令。

你的任务：
1. 从上一个智能体的消息中提取要执行的命令（EXECUTE_COMMAND之前的内容）
2. 调用execute_command_tool工具在主机 {host} 上执行该命令
3. 将工具返回的完整结果直接输出给用户，不要修改或总结

重要：直接返回工具执行的原始结果，然后添加 TERMINATE""",
            model_client=client,
            tools=[execute_command_tool],
        )
        
        # 创建RoundRobinGroupChat团队
        team = RoundRobinGroupChat(
            participants=[command_generator, command_analyzer, command_optimizer, command_executor],
            termination_condition=TextMentionTermination("TERMINATE") | MaxMessageTermination(15)
        )
        
        # 运行团队处理
        result = await team.run(task=request_text)
        
        if not result or not result.messages:
            return "❌ 命令处理团队执行失败"
        
        # 提取最终结果 - 查找CommandExecutor的工具执行结果
        for message in reversed(result.messages):
            if hasattr(message, 'content'):
                content = message.content.replace("TERMINATE", "").strip()
                # 如果内容包含SSH执行结果的标识，说明这是我们要的结果
                if content and ("命令执行结果" in content or "SSH操作失败" in content or "无法连接到主机" in content):
                    logger.info(f"[SSH-COMMAND-TEAM] 找到SSH执行结果: {content[:100]}...")
                    return content
                # 如果是工具调用的结果，也返回
                elif content and len(content) > 50 and "工具返回" not in content:
                    logger.info(f"[SSH-COMMAND-TEAM] 找到执行结果: {content[:100]}...")
                    return content
        
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH工具模块，支持自由模式和一键升级模式
"""

import re
from typing import Dict, Any, List
from loguru import logger

from app.services.ssh.client import SSHClient, SSHManager
from app.core.config import settings

async def process_ssh_request(
    request_text: str,
    host: str,
    mode: str = "free",  # free 或 upgrade
    sender_id: str = None,
    conversation_id: str = None
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
    # 提取可能的命令意图
    command = await _extract_command_intent(request_text)
    if not command:
        return "⚠️ 无法从您的请求中提取有效命令，请更明确地说明您想执行的操作"
    
    # 执行SSH命令
    client = SSHClient(host)
    connected = await client.connect()
    if not connected:
        return f"❌ 无法连接到主机 {host}"
    
    exit_code, stdout, stderr = await client.execute_command(command)
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
        "docker compose up -d"
    ]
    
    full_command = " && ".join(upgrade_commands)
    client = SSHClient(host)
    connected = await client.connect()
    if not connected:
        return f"❌ 无法连接到主机 {host}"
    
    exit_code, stdout, stderr = await client.execute_command(full_command)
    client.close()
    
    # 格式化升级结果
    result = f"## 🚀 Dify服务升级执行结果 ({host})\n"
    result += f"**执行的命令:**\n```bash\n{full_command}\n```\n"
    
    if exit_code == 0:
        result += "✅ 升级命令执行成功\n"
        result += f"**输出:**\n```\n{stdout}\n```"
    else:
        result += "❌ 升级命令执行失败\n"
        result += f"**错误代码:** {exit_code}\n"
        result += f"**错误输出:**\n```\n{stderr}\n```"
    
    return result

async def _extract_command_intent(text: str) -> str:
    """使用AI智能体从用户文本生成合适的SSH命令"""
    from app.services.ai.openai_client import OpenAIClient
    
    prompt = f"""
    你是一个Linux系统管理员，需要根据用户请求生成合适的SSH命令。
    用户请求: {text}
    
    请遵循以下规则:
    1. 只返回可直接执行的命令，不要包含任何解释
    2. 确保命令安全，不要执行危险操作
    3. 优先使用标准Linux命令
    4. 如果需要sudo权限，请明确添加sudo
    
    生成的命令:
    """
    
    try:
        client = OpenAIClient()
        response = await client.generate_text(prompt, max_tokens=50)
        return response.strip()
    except Exception as e:
        logger.error(f"AI命令生成失败: {e}")
        return text.strip()  # 失败时返回原始文本

def _format_command_result(host: str, command: str, exit_code: int, stdout: str, stderr: str) -> str:
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
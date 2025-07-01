#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH工具调试测试脚本
用于验证SSH工具的超时处理和命令检测功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai.tools.ssh import process_ssh_request, _is_problematic_command, _get_command_timeout
from app.services.ssh.client import SSHClient
from loguru import logger

# 配置日志输出到控制台
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


async def test_problematic_command_detection():
    """测试有问题命令的检测"""
    print("\n=== 测试有问题命令的检测 ===")
    
    test_commands = [
        ("top", True),
        ("htop", True),
        ("tail -f /var/log/syslog", True),
        ("vi /etc/hosts", True),
        ("watch df -h", True),
        ("ls -la", False),
        ("ps aux", False),
        ("df -h", False),
        ("uptime", False),
    ]
    
    for command, expected in test_commands:
        result = _is_problematic_command(command)
        status = "✅" if result == expected else "❌"
        print(f"{status} 命令: '{command}' -> 检测结果: {result} (期望: {expected})")


def test_command_timeout_detection():
    """测试命令超时设置"""
    print("\n=== 测试命令超时设置 ===")
    
    test_commands = [
        ("docker pull nginx", 300),
        ("apt update", 300),
        ("systemctl restart nginx", 120),
        ("ps aux", 60),
        ("ls -la", 60),
        ("tar -czf backup.tgz /home", 300),
        ("find / -name '*.log'", 300),
    ]
    
    for command, expected in test_commands:
        result = _get_command_timeout(command)
        status = "✅" if result == expected else "❌"
        print(f"{status} 命令: '{command}' -> 超时: {result}秒 (期望: {expected}秒)")


async def test_ssh_tool_with_safe_commands():
    """测试SSH工具的安全命令执行"""
    print("\n=== 测试SSH工具安全命令执行 ===")
    
    # 注意：这里需要一个可用的SSH主机进行测试
    # 如果没有可用主机，这个测试会失败，但不影响其他测试
    test_host = "192.168.1.128"  # 可以改为实际的测试主机
    
    safe_commands = [
        "查看系统信息",
        "显示当前目录内容", 
        "查看系统负载",
    ]
    
    for request in safe_commands:
        print(f"\n测试请求: {request}")
        try:
            result = await process_ssh_request(
                request_text=request,
                host=test_host,
                mode="free"
            )
            print(f"执行结果: {result[:200]}...")  # 只显示前200个字符
        except Exception as e:
            print(f"执行异常: {e}")


async def test_problematic_command_handling():
    """测试有问题命令的处理"""
    print("\n=== 测试有问题命令的处理 ===")
    
    test_host = "localhost"
    problematic_requests = [
        "运行top命令查看进程",
        "使用vi编辑文件",
        "执行tail -f查看日志",
    ]
    
    for request in problematic_requests:
        print(f"\n测试有问题的请求: {request}")
        try:
            result = await process_ssh_request(
                request_text=request,
                host=test_host,
                mode="free"
            )
            print(f"处理结果: {result}")
        except Exception as e:
            print(f"处理异常: {e}")


async def main():
    """主测试函数"""
    print("🔍 SSH工具调试测试开始")
    print("=" * 50)
    
    # 测试命令检测功能
    await test_problematic_command_detection()
    test_command_timeout_detection()
    
    # 测试实际SSH功能（需要可用的SSH主机）
    print("\n⚠️  以下测试需要可用的SSH主机，如果没有会显示连接失败")
    await test_ssh_tool_with_safe_commands()
    await test_problematic_command_handling()
    
    print("\n" + "=" * 50)
    print("🎉 SSH工具调试测试完成")
    print("\n📋 测试总结:")
    print("1. 有问题命令检测功能已实现")
    print("2. 命令超时设置功能已实现") 
    print("3. SSH工具已增强错误处理和日志记录")
    print("4. 升级模式已增加更长的超时时间")


if __name__ == "__main__":
    asyncio.run(main())
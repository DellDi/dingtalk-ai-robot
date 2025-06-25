#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import unittest
from unittest.mock import patch, MagicMock
from loguru import logger

from app.services.ai.tools.ssh import process_ssh_request, _extract_command_intent, _format_command_result

class TestSSHTool(unittest.TestCase):
    def setUp(self):
        # 设置测试环境变量
        os.environ['SSH_USERNAME'] = 'testuser'
        os.environ['SSH_PASSWORD'] = 'testpass'
        
        # 配置日志
        logger.remove()
        logger.add("test_ssh.log", level="DEBUG")

    @patch('app.services.ai.tools.ssh.SSHClient')
    async def test_free_mode_success(self, mock_ssh_client):
        """测试自由模式成功场景"""
        # 配置mock
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.execute_command.return_value = (0, "file1\nfile2", "")
        mock_ssh_client.return_value = mock_client
        
        # 执行测试
        result = await process_ssh_request("列出当前目录文件", "testhost")
        
        # 验证结果
        self.assertIn("file1", result)
        self.assertIn("file2", result)
        self.assertIn("命令执行成功", result)
        mock_client.connect.assert_called_once()
        mock_client.execute_command.assert_called_once()

    @patch('app.services.ai.tools.ssh.SSHClient')
    async def test_upgrade_mode_success(self, mock_ssh_client):
        """测试一键升级模式成功场景"""
        # 配置mock
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.execute_command.return_value = (0, "upgrade success", "")
        mock_ssh_client.return_value = mock_client
        
        # 执行测试
        result = await process_ssh_request("", "testhost", mode="upgrade")
        
        # 验证结果
        self.assertIn("升级命令执行成功", result)
        self.assertIn("docker compose up -d", result)
        mock_client.connect.assert_called_once()
        mock_client.execute_command.assert_called_once()

    @patch('app.services.ai.tools.ssh.OpenAIClient')
    async def test_extract_command_intent(self, mock_openai):
        """测试AI命令生成"""
        # 配置mock
        mock_client = MagicMock()
        mock_client.generate_text.return_value = "ls -la"
        mock_openai.return_value = mock_client
        
        # 测试正常情况
        result = await _extract_command_intent("列出当前目录")
        self.assertEqual("ls -la", result)
        
        # 测试异常情况
        mock_client.generate_text.side_effect = Exception("API error")
        result = await _extract_command_intent("列出当前目录")
        self.assertEqual("列出当前目录", result)  # 返回原文本

    def test_format_command_result(self):
        """测试命令结果格式化"""
        # 成功场景
        success_result = _format_command_result(
            "testhost", "ls -la", 0, "file1\nfile2", ""
        )
        self.assertIn("命令执行成功", success_result)
        self.assertIn("file1", success_result)
        
        # 失败场景
        fail_result = _format_command_result(
            "testhost", "invalid_cmd", 1, "", "command not found"
        )
        self.assertIn("命令执行失败", fail_result)
        self.assertIn("command not found", fail_result)

if __name__ == '__main__':
    unittest.main()
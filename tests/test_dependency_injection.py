#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
依赖注入架构测试模块
"""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

from app.core.container import container, ApplicationContainer
from app.services.knowledge.retriever import KnowledgeRetriever
from app.services.ai.handler import AIMessageHandler
from app.services.ssh.client import SSHClient


class TestDependencyInjection:
    """依赖注入测试类"""

    def test_container_initialization(self):
        """测试容器初始化"""
        # 检查容器是否正确创建
        assert isinstance(container, ApplicationContainer)
        
        # 检查提供者是否注册
        assert hasattr(container, 'knowledge_retriever')
        assert hasattr(container, 'ai_message_handler')
        assert hasattr(container, 'ssh_client')

    def test_singleton_provider(self):
        """测试单例提供者"""
        # 获取两次实例，应该是同一个对象
        instance1 = container.knowledge_retriever()
        instance2 = container.knowledge_retriever()
        
        assert instance1 is instance2
        assert isinstance(instance1, KnowledgeRetriever)

    def test_factory_provider(self):
        """测试工厂提供者"""
        # 获取两次实例，应该是不同的对象
        instance1 = container.ssh_client()
        instance2 = container.ssh_client()
        
        assert instance1 is not instance2
        assert isinstance(instance1, SSHClient)
        assert isinstance(instance2, SSHClient)

    def test_provider_override(self):
        """测试提供者覆盖（用于测试）"""
        # 创建模拟对象
        mock_retriever = Mock(spec=KnowledgeRetriever)
        
        # 覆盖提供者
        container.knowledge_retriever.override(mock_retriever)
        
        # 获取实例应该是模拟对象
        instance = container.knowledge_retriever()
        assert instance is mock_retriever
        
        # 重置覆盖
        container.knowledge_retriever.reset_override()
        
        # 获取实例应该是真实对象
        instance = container.knowledge_retriever()
        assert instance is not mock_retriever
        assert isinstance(instance, KnowledgeRetriever)

    def test_dependency_injection_functions(self):
        """测试依赖注入函数"""
        from app.core.container import (
            get_knowledge_retriever,
            get_ai_message_handler,
            get_ssh_client
        )
        
        # 测试获取函数
        retriever = get_knowledge_retriever()
        ai_handler = get_ai_message_handler()
        ssh_client = get_ssh_client()
        
        assert isinstance(retriever, KnowledgeRetriever)
        assert isinstance(ai_handler, AIMessageHandler)
        assert isinstance(ssh_client, SSHClient)

    @pytest.mark.asyncio
    async def test_async_dependency_functions(self):
        """测试异步依赖注入函数"""
        from app.core.container import (
            get_knowledge_retriever_dependency,
            get_ai_handler_dependency,
            get_ssh_client_dependency
        )
        
        # 测试异步获取函数
        retriever = await get_knowledge_retriever_dependency()
        ai_handler = await get_ai_handler_dependency()
        ssh_client = await get_ssh_client_dependency()
        
        assert isinstance(retriever, KnowledgeRetriever)
        assert isinstance(ai_handler, AIMessageHandler)
        assert isinstance(ssh_client, SSHClient)


class TestServiceIntegration:
    """服务集成测试类"""

    def test_service_dependencies(self):
        """测试服务间依赖关系"""
        # 获取周报服务，它依赖其他服务
        weekly_service = container.weekly_report_service()
        
        # 检查依赖是否正确注入
        assert hasattr(weekly_service, 'dingtalk_service')
        assert hasattr(weekly_service, 'ai_agent')

    def test_configuration_injection(self):
        """测试配置注入"""
        # 获取知识库检索器
        retriever = container.knowledge_retriever()
        
        # 检查配置是否正确注入
        assert hasattr(retriever, 'collection_name')
        assert hasattr(retriever, 'persistence_path')


class TestMockingWithDI:
    """依赖注入模拟测试类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        # 保存原始提供者
        self.original_providers = {}

    def teardown_method(self):
        """每个测试方法后的清理"""
        # 重置所有覆盖
        container.knowledge_retriever.reset_override()
        container.ai_message_handler.reset_override()
        container.ssh_client.reset_override()

    @pytest.mark.asyncio
    async def test_mock_knowledge_retriever(self):
        """测试模拟知识库检索器"""
        # 创建模拟对象
        mock_retriever = AsyncMock(spec=KnowledgeRetriever)
        mock_retriever.initialized = True
        mock_retriever.search.return_value = [
            {"content": "测试内容", "metadata": {"score": 0.9}}
        ]
        
        # 覆盖提供者
        container.knowledge_retriever.override(mock_retriever)
        
        # 测试依赖注入
        from app.core.container import get_knowledge_retriever_dependency
        
        retriever = await get_knowledge_retriever_dependency()
        assert retriever is mock_retriever
        
        # 测试模拟方法
        results = await retriever.search("测试查询")
        assert len(results) == 1
        assert results[0]["content"] == "测试内容"

    def test_mock_ai_handler(self):
        """测试模拟AI处理器"""
        # 创建模拟对象
        mock_handler = Mock(spec=AIMessageHandler)
        mock_handler.process_message.return_value = "模拟AI响应"
        
        # 覆盖提供者
        container.ai_message_handler.override(mock_handler)
        
        # 测试依赖注入
        from app.core.container import get_ai_message_handler
        
        handler = get_ai_message_handler()
        assert handler is mock_handler
        
        # 测试模拟方法
        response = handler.process_message("测试消息", "user1", "conv1")
        assert response == "模拟AI响应"


class TestErrorHandling:
    """错误处理测试类"""

    def test_service_unavailable_exception(self):
        """测试服务不可用异常"""
        from app.core.exceptions import ServiceUnavailableException
        
        # 创建异常
        exc = ServiceUnavailableException("TestService", {"reason": "配置错误"})
        
        assert exc.service_name == "TestService"
        assert exc.details["reason"] == "配置错误"
        assert "TestService" in str(exc)

    def test_exception_to_http_conversion(self):
        """测试异常转HTTP异常"""
        from app.core.exceptions import ServiceUnavailableException, service_exception_to_http
        
        # 创建服务异常
        service_exc = ServiceUnavailableException("TestService")
        
        # 转换为HTTP异常
        http_exc = service_exception_to_http(service_exc)
        
        assert http_exc.status_code == 503
        assert "TestService" in str(http_exc.detail)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

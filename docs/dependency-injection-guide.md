# 依赖注入架构指南

## 📋 概述

本项目采用了现代化的依赖注入（Dependency Injection, DI）架构，使用 `dependency-injector` 框架实现控制反转（IoC），提高代码的可测试性、可维护性和可扩展性。

## 🏗️ 架构设计

### 核心组件

1. **容器（Container）** - `app/core/container.py`
   - 管理所有服务的生命周期
   - 配置服务间的依赖关系
   - 提供统一的服务获取接口

2. **服务提供者（Providers）**
   - `Singleton`: 单例模式，适用于无状态服务
   - `Factory`: 工厂模式，每次调用创建新实例
   - `Configuration`: 配置提供者

3. **依赖注入函数** - FastAPI集成
   - 通过 `Depends()` 机制注入服务
   - 自动处理服务初始化和错误

## 🔧 使用方法

### 1. 服务注册

在 `app/core/container.py` 中注册新服务：

```python
class ApplicationContainer(containers.DeclarativeContainer):
    # 单例服务
    my_service = providers.Singleton(
        MyService,
        config_param=settings.MY_CONFIG,
    )
    
    # 工厂服务
    my_factory = providers.Factory(
        MyFactory,
        param1="value1",
    )
```

### 2. API端点中使用

```python
from fastapi import APIRouter, Depends
from app.core.container import get_my_service_dependency

@router.get("/example")
async def example_endpoint(
    my_service: MyService = Depends(get_my_service_dependency)
):
    result = await my_service.do_something()
    return {"result": result}
```

### 3. 服务间依赖

```python
# 在容器中配置服务依赖
service_a = providers.Singleton(ServiceA)
service_b = providers.Singleton(
    ServiceB,
    dependency=service_a,  # ServiceB依赖ServiceA
)
```

## 🎯 优势对比

### 传统方式 vs 依赖注入

| 方面 | 传统方式 | 依赖注入 |
|------|----------|----------|
| **耦合度** | 高耦合，直接实例化 | 松耦合，通过接口依赖 |
| **测试性** | 难以模拟依赖 | 易于注入Mock对象 |
| **配置** | 硬编码配置 | 集中化配置管理 |
| **生命周期** | 手动管理 | 自动管理 |
| **扩展性** | 修改代码 | 配置驱动 |

### 代码示例对比

**传统方式：**
```python
# 紧耦合，难以测试
async def search_endpoint(request: SearchRequest):
    # 硬编码依赖
    retriever = KnowledgeRetriever(
        collection_name="default",
        persistence_path="./data"
    )
    await retriever.initialize()
    results = await retriever.search(request.query)
    return results
```

**依赖注入方式：**
```python
# 松耦合，易于测试
async def search_endpoint(
    request: SearchRequest,
    retriever: KnowledgeRetriever = Depends(get_knowledge_retriever_dependency)
):
    # 自动注入，已初始化
    results = await retriever.search(request.query)
    return results
```

## 🧪 测试支持

### 单元测试

```python
import pytest
from unittest.mock import Mock
from app.core.container import container

def test_service_with_mock():
    # 覆盖容器中的服务
    mock_service = Mock()
    container.my_service.override(mock_service)
    
    # 测试代码
    service = container.my_service()
    assert service is mock_service
    
    # 重置覆盖
    container.my_service.reset_override()
```

### 集成测试

```python
@pytest.fixture
def test_container():
    # 创建测试专用容器
    test_container = ApplicationContainer()
    test_container.config.from_dict({
        "test_mode": True,
        "database_url": "sqlite:///:memory:"
    })
    return test_container
```

## 📊 性能监控

### 服务状态检查

访问 `/demo/service-status` 端点查看所有注入服务的状态：

```json
{
  "service_name": "KnowledgeRetriever",
  "status": "healthy",
  "details": {
    "initialized": true,
    "collection_name": "global_knowledge_base",
    "retrieve_k": 20
  }
}
```

### 集成查询演示

访问 `/demo/integrated-query` 端点体验多服务协作：

```json
{
  "query": "什么是依赖注入？",
  "include_knowledge": true,
  "include_ai_analysis": true,
  "execute_command": "echo 'Hello DI!'"
}
```

## 🔍 调试和监控

### 日志记录

所有服务操作都会记录详细日志：

```
2024-01-01 10:00:00 | INFO | 🔧 开始初始化依赖注入容器...
2024-01-01 10:00:01 | INFO | ✅ 知识库检索器初始化成功
2024-01-01 10:00:02 | INFO | 🎉 依赖注入容器初始化完成
```

### 响应头信息

每个API响应都包含依赖注入相关的头信息：

```
X-DI-Context: enabled
X-Request-ID: 1704096000000
X-Process-Time: 0.123
```

## 🚀 最佳实践

### 1. 服务设计原则

- **单一职责**：每个服务只负责一个业务领域
- **接口隔离**：定义清晰的服务接口
- **依赖倒置**：依赖抽象而非具体实现

### 2. 生命周期管理

- **Singleton**：用于无状态服务或需要共享状态
- **Factory**：用于有状态服务或需要隔离的服务
- **异步初始化**：在应用启动时初始化异步服务

### 3. 错误处理

- 使用自定义异常类型
- 统一的异常处理中间件
- 详细的错误日志记录

### 4. 配置管理

- 环境变量驱动配置
- 类型安全的配置类
- 配置验证和默认值

## 📈 扩展指南

### 添加新服务

1. **定义服务类**
```python
class NewService:
    def __init__(self, config_param: str):
        self.config_param = config_param
    
    async def do_work(self) -> str:
        return f"Working with {self.config_param}"
```

2. **注册到容器**
```python
# 在 ApplicationContainer 中添加
new_service = providers.Singleton(
    NewService,
    config_param=settings.NEW_SERVICE_CONFIG,
)
```

3. **创建依赖函数**
```python
def get_new_service_dependency() -> NewService:
    return container.new_service()
```

4. **在API中使用**
```python
@router.get("/new-endpoint")
async def new_endpoint(
    service: NewService = Depends(get_new_service_dependency)
):
    result = await service.do_work()
    return {"result": result}
```

## 🎉 总结

依赖注入架构为项目带来了：

- ✅ **更好的代码组织**：清晰的服务边界和依赖关系
- ✅ **更高的可测试性**：易于进行单元测试和集成测试
- ✅ **更强的可维护性**：松耦合的设计便于修改和扩展
- ✅ **更好的性能**：统一的生命周期管理和资源优化
- ✅ **更强的可观测性**：完整的日志记录和监控支持

通过这种架构，我们实现了现代化的、可扩展的、易于维护的应用程序设计。

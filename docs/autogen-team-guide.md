# AutoGen Team 模式完整指南

## 目录

1. [概述](#概述)
2. [Team 类型](#team-类型)
3. [创建团队](#创建团队)
4. [团队执行](#团队执行)
5. [流式处理与日志记录](#流式处理与日志记录)
6. [终止条件](#终止条件)
7. [高级功能](#高级功能)
8. [最佳实践](#最佳实践)
9. [常见问题与解决方案](#常见问题与解决方案)

## 概述

AutoGen Team 是 AutoGen 框架中用于创建和管理多智能体系统的组件。它提供了一种结构化方式来组织多个智能体协同工作，处理复杂任务。Team 模式特别适合以下场景：

- 需要多种专业知识协作的复杂任务
- 需要审查和反馈的工作流程
- 涉及多步骤处理的任务链
- 需要不同角色分工的项目

## Team 类型

AutoGen 提供多种 Team 实现，每种都有其特定用途和工作方式：

### 1. RoundRobinGroupChat

最简单的团队类型，智能体按照固定顺序轮流发言。这种模式适合有明确角色分工、需要依次处理的场景。

```python
from autogen_agentchat.teams import RoundRobinGroupChat

team = RoundRobinGroupChat(
    participants=[agent1, agent2, agent3],
    termination_condition=termination_condition
)
```

### 2. SelectorGroupChat

使用一个专门的选择器来动态决定下一个应该发言的智能体。选择器可以是一个 LLM 模型，它会分析当前对话状态，选择最合适的智能体继续对话。

```python
from autogen_agentchat.teams import SelectorGroupChat

team = SelectorGroupChat(
    participants=[agent1, agent2, agent3],
    selector=selector_agent,  # 负责选择下一个发言者
    termination_condition=termination_condition
)
```

### 3. MagenticOneGroupChat

一个专门设计用于解决开放式网络和文件任务的通用多智能体系统。它包含了一组预配置的智能体，专门用于处理各种复杂任务。

```python
from autogen_ext.teams.magentic_one import MagenticOne

team = MagenticOne(
    model_client=model_client,
    # 其他配置...
)
```

### 4. Swarm

使用 HandoffMessage 信号在智能体之间传递控制权的团队模式。这种模式允许智能体显式地将控制权传递给特定的其他智能体。

```python
from autogen_agentchat.teams import Swarm
from autogen_agentchat.messages import HandoffMessage

team = Swarm(
    agents=[agent1, agent2, agent3],
    termination_condition=termination_condition
)
```

## 创建团队

创建团队的基本步骤包括：

1. 初始化各个智能体
2. 定义终止条件
3. 创建团队实例

示例代码：

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

# 1. 创建模型客户端
model_client = OpenAIChatCompletionClient(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY")
)

# 2. 创建智能体
assistant_agent = AssistantAgent(
    name="assistant",
    model_client=model_client,
    system_message="你是一个助手，负责回答用户问题。"
)

critic_agent = AssistantAgent(
    name="critic",
    model_client=model_client,
    system_message="你是一个评论家，负责审查和评价助手的回答。当你认为回答很好时，回复'APPROVE'。"
)

# 3. 定义终止条件
termination_condition = TextMentionTermination("APPROVE")

# 4. 创建团队
team = RoundRobinGroupChat(
    participants=[assistant_agent, critic_agent],
    termination_condition=termination_condition
)
```

## 团队执行

AutoGen Team 提供两种主要的执行方式：`run()` 和 `run_stream()`。

### run() 方法

`run()` 方法会运行团队直到终止条件满足，然后返回一个 `TaskResult` 对象。

```python
# 在异步环境中
result = await team.run(task="解释什么是量子计算")

# 在同步环境中
result = asyncio.run(team.run(task="解释什么是量子计算"))
```

### run_stream() 方法

`run_stream()` 方法以流的形式返回团队执行过程中产生的每一条消息，可以用于实时显示和处理。

```python
async for message in team.run_stream(task="解释什么是量子计算"):
    if isinstance(message, TaskResult):
        print("任务完成，原因:", message.stop_reason)
    else:
        print(f"[{message.source}] {message.content}")
```

## 流式处理与日志记录

### Console 类

AutoGen 提供了 `Console` 类，可以直观地显示团队执行过程中的消息流。

```python
from autogen_agentchat.ui import Console

# 直接显示所有消息
result = await Console(team.run_stream(task="解释什么是量子计算"))

# 也可以自定义显示
async for message in team.run_stream(task="解释什么是量子计算"):
    # 自定义处理每条消息
    pass
```

### 日志记录

可以结合 `loguru` 等日志库记录团队执行过程：

```python
from loguru import logger

async for message in team.run_stream(task="解释什么是量子计算"):
    if isinstance(message, TaskResult):
        logger.info(f"任务完成，原因: {message.stop_reason}")
    else:
        logger.debug(f"[{message.source}] {message.content[:100]}...")
```

## 终止条件

团队终止条件决定了团队何时停止执行。AutoGen 提供多种终止条件：

### TextMentionTermination

当消息中包含特定文本时终止：

```python
from autogen_agentchat.conditions import TextMentionTermination

termination = TextMentionTermination("DONE")  # 当消息中出现"DONE"时终止
```

### RegexTermination

基于正则表达式匹配终止：

```python
from autogen_agentchat.conditions import RegexTermination

termination = RegexTermination(r"TASK[\s_-]*COMPLETE")  # 匹配"TASK COMPLETE"等模式
```

### ExternalTermination

由外部条件控制终止：

```python
from autogen_agentchat.conditions import ExternalTermination

external_termination = ExternalTermination()
team = RoundRobinGroupChat(
    participants=[agent1, agent2],
    termination_condition=external_termination
)

# 在适当时机触发终止
external_termination.terminate()
```

### 组合终止条件

可以组合多个终止条件：

```python
from autogen_agentchat.conditions import AnyTermination, AllTermination

# 任何一个条件满足时终止
any_termination = AnyTermination([condition1, condition2])

# 所有条件都满足时终止
all_termination = AllTermination([condition1, condition2])
```

## 高级功能

### 1. 取消执行

可以使用 `CancellationToken` 随时取消团队执行：

```python
from autogen_core import CancellationToken

# 创建取消令牌
cancellation_token = CancellationToken()

# 启动团队任务
task = asyncio.create_task(
    team.run(
        task="执行长时间任务",
        cancellation_token=cancellation_token
    )
)

# 在需要时取消
cancellation_token.cancel()

try:
    result = await task  # 这里会抛出 CancelledError
except asyncio.CancelledError:
    print("任务已取消")
```

### 2. 重置团队状态

可以使用 `reset()` 方法重置团队状态，清除之前的对话历史：

```python
await team.reset()  # 重置团队状态
```

### 3. 人机交互

可以加入 `UserProxyAgent` 实现人机交互：

```python
from autogen_agentchat.agents import UserProxyAgent

user_proxy = UserProxyAgent(
    name="user",
    human_input_mode="ALWAYS"  # 总是请求人类输入
)

team = RoundRobinGroupChat(
    participants=[user_proxy, assistant_agent],
    termination_condition=termination_condition
)
```

### 4. 自定义状态追踪

可以扩展基础团队类实现自定义状态追踪：

```python
class CustomTeam(RoundRobinGroupChat):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_state = {}
    
    async def run(self, *args, **kwargs):
        # 在执行前初始化状态
        self.custom_state = {"start_time": time.time()}
        result = await super().run(*args, **kwargs)
        # 在执行后记录状态
        self.custom_state["end_time"] = time.time()
        self.custom_state["duration"] = self.custom_state["end_time"] - self.custom_state["start_time"]
        return result
```

## 最佳实践

### 1. 团队设计原则

- **明确的角色分工**：每个智能体应该有明确的职责和专长
- **简单优先**：从简单团队开始，根据需要逐步扩展
- **精确的系统提示**：为每个智能体提供清晰、详细的系统提示
- **适当的终止条件**：选择合适的终止条件，避免无限循环

### 2. 性能优化

- **合理控制团队规模**：团队成员越多，协调成本越高
- **智能选择模型**：关键智能体使用高级模型，辅助智能体可以使用轻量级模型
- **使用流式处理**：长时间任务使用 `run_stream()` 实时显示进度

### 3. 错误处理

- **使用异常处理**：捕获并处理可能的异常
- **实现重试机制**：对可能失败的操作添加重试逻辑
- **记录详细日志**：记录团队执行的每个步骤，便于调试

```python
try:
    result = await team.run(task="复杂任务")
except Exception as e:
    logger.error(f"团队执行失败: {e}")
    # 实现重试逻辑
    for attempt in range(3):
        try:
            await team.reset()
            result = await team.run(task="复杂任务")
            break
        except Exception as retry_e:
            logger.error(f"重试 {attempt+1} 失败: {retry_e}")
```

### 4. 状态监控

- **监控处理进度**：使用 `run_stream()` 实时监控执行进度
- **保存中间结果**：保存重要的中间结果，防止失败时丢失
- **设置超时机制**：防止任务无限执行

## 常见问题与解决方案

### 1. 团队无限循环

**问题**：团队执行不停止，智能体一直在对话。

**解决方案**：
- 设置更严格的终止条件
- 为智能体添加明确的结束指示
- 使用 `CancellationToken` 和超时机制

```python
# 设置超时机制
async def run_with_timeout(team, task, timeout=60):
    cancellation_token = CancellationToken()
    
    # 创建任务
    team_task = asyncio.create_task(
        team.run(
            task=task,
            cancellation_token=cancellation_token
        )
    )
    
    # 设置超时
    try:
        return await asyncio.wait_for(team_task, timeout=timeout)
    except asyncio.TimeoutError:
        cancellation_token.cancel()
        logger.warning(f"任务已超时 ({timeout}秒)")
        return None
```

### 2. 智能体角色混淆

**问题**：智能体不遵循其定义的角色，尝试执行其他智能体的工作。

**解决方案**：
- 优化系统提示，更明确地定义角色边界
- 添加审查智能体，监督和纠正角色偏离
- 使用更结构化的消息格式

### 3. 消息格式不一致

**问题**：智能体输出格式不一致，导致后续处理困难。

**解决方案**：
- 在系统提示中明确要求特定的输出格式
- 添加格式验证智能体
- 实现输出格式的后处理

```python
format_validator = AssistantAgent(
    name="validator",
    model_client=model_client,
    system_message="检查上一个智能体的输出是否符合JSON格式。如果不符合，请指出问题并要求修正。符合格式时回复'FORMAT_VALID'。"
)
```

### 4. 资源消耗过高

**问题**：多智能体系统消耗大量资源和API调用。

**解决方案**：
- 优化团队规模，移除不必要的智能体
- 为不同角色使用不同级别的模型
- 实现缓存机制，避免重复计算

---

这份指南涵盖了 AutoGen Team 模式的主要概念、API 和最佳实践。通过合理使用这些功能，可以构建强大的多智能体系统，解决复杂问题。在实际应用中，应根据具体任务需求调整团队结构和执行策略，以达到最佳效果。

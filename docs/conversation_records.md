# 对话记录功能文档

## 概述

对话记录功能用于记录钉钉用户与智能体之间的所有对话信息，包括用户提问、智能体回复、响应时间、使用的智能体类型等详细信息。这个功能有助于：

- 📊 分析用户使用模式
- 🔍 追踪对话历史
- ⚡ 监控系统性能
- 📈 生成使用统计报告

## 数据库表结构

### conversation_records 表

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| id | INTEGER | 主键 | PRIMARY KEY, AUTOINCREMENT |
| conversation_id | TEXT | 钉钉会话ID（群聊或单聊） | NOT NULL |
| sender_id | TEXT | 发送者钉钉用户ID | NOT NULL |
| user_question | TEXT | 用户提问内容 | NOT NULL |
| ai_response | TEXT | 智能体回复内容 | NOT NULL |
| message_type | TEXT | 消息类型（text/markdown/card等） | DEFAULT 'text' |
| response_time_ms | INTEGER | 响应时间（毫秒） | NULL |
| agent_type | TEXT | 处理的智能体类型 | NULL |
| created_at | DATETIME | 创建时间 | DEFAULT CURRENT_TIMESTAMP |
| updated_at | DATETIME | 更新时间 | DEFAULT CURRENT_TIMESTAMP |

### 索引

- `idx_conversation_records_conversation_id`: 按会话ID索引
- `idx_conversation_records_sender_id`: 按发送者ID索引  
- `idx_conversation_records_created_at`: 按创建时间索引

## 核心功能

### 1. 自动记录对话

系统会在 `AIMessageHandler.process_message()` 方法中自动记录每次对话：

```python
# 记录开始时间
start_time = time.time()

# 处理消息...

# 计算响应时间并保存记录
end_time = time.time()
response_time_ms = int((end_time - start_time) * 1000)

save_conversation_record(
    conversation_id=conversation_id,
    sender_id=sender_id,
    user_question=text,
    ai_response=final_reply,
    message_type="text",
    response_time_ms=response_time_ms,
    agent_type=agent_type,
)
```

### 2. 数据库操作函数

#### save_conversation_record()
保存对话记录到数据库

```python
def save_conversation_record(
    conversation_id: str,
    sender_id: str,
    user_question: str,
    ai_response: str,
    message_type: str = "text",
    response_time_ms: Optional[int] = None,
    agent_type: Optional[str] = None,
) -> int
```

#### get_conversation_history()
获取对话历史记录

```python
def get_conversation_history(
    conversation_id: Optional[str] = None,
    sender_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Tuple]
```

#### get_conversation_stats()
获取对话统计信息

```python
def get_conversation_stats(
    conversation_id: Optional[str] = None,
    sender_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]
```

## API 接口

### 1. 获取对话历史

**GET** `/api/v1/conversation/history`

**查询参数：**
- `conversation_id` (可选): 会话ID
- `sender_id` (可选): 发送者ID
- `limit` (可选): 返回记录数量限制，默认50
- `offset` (可选): 偏移量，默认0

**响应示例：**
```json
{
  "success": true,
  "message": "获取对话历史成功",
  "data": [
    {
      "id": 1,
      "conversation_id": "conv_123",
      "sender_id": "user_456",
      "user_question": "今天天气怎么样？",
      "ai_response": "今天天气晴朗，温度适宜。",
      "message_type": "text",
      "response_time_ms": 1200,
      "agent_type": "WeatherAgent",
      "created_at": "2024-01-01 10:00:00",
      "updated_at": "2024-01-01 10:00:00"
    }
  ],
  "total": 1
}
```

### 2. 获取对话统计

**GET** `/api/v1/conversation/stats`

**查询参数：**
- `conversation_id` (可选): 会话ID
- `sender_id` (可选): 发送者ID
- `start_date` (可选): 开始日期 (YYYY-MM-DD)
- `end_date` (可选): 结束日期 (YYYY-MM-DD)

**响应示例：**
```json
{
  "success": true,
  "message": "获取对话统计成功",
  "data": {
    "total_conversations": 150,
    "unique_users": 25,
    "unique_conversations": 45,
    "avg_response_time_ms": 1850.5,
    "first_conversation": "2024-01-01 09:00:00",
    "last_conversation": "2024-01-01 18:00:00",
    "agent_distribution": [
      {"agent_type": "GeneralAgent", "count": 60},
      {"agent_type": "WeatherAgent", "count": 30},
      {"agent_type": "JiraAgent", "count": 25}
    ],
    "message_type_distribution": [
      {"message_type": "text", "count": 120},
      {"message_type": "markdown", "count": 30}
    ]
  }
}
```

### 3. 获取最近对话

**GET** `/api/v1/conversation/recent`

**查询参数：**
- `hours` (可选): 最近几小时内的对话，默认24小时
- `limit` (可选): 返回记录数量限制，默认100

### 4. 获取用户对话摘要

**GET** `/api/v1/conversation/user/{user_id}/summary`

**路径参数：**
- `user_id`: 用户ID

**查询参数：**
- `days` (可选): 统计天数，默认7天

## 使用场景

### 1. 用户行为分析
```python
# 获取某用户最近7天的对话统计
stats = get_conversation_stats(
    sender_id="user_123",
    start_date="2024-01-01",
    end_date="2024-01-07"
)
```

### 2. 系统性能监控
```python
# 获取平均响应时间
stats = get_conversation_stats()
avg_response_time = stats['avg_response_time_ms']
```

### 3. 智能体使用分析
```python
# 分析各智能体的使用频率
stats = get_conversation_stats()
agent_distribution = stats['agent_distribution']
```

## 测试

运行测试脚本验证功能：

```bash
python scripts/test_conversation_records.py
```

测试脚本会：
1. 检查数据库表结构
2. 插入测试数据
3. 验证查询功能
4. 测试统计功能
5. 清理测试数据

## 注意事项

1. **性能考虑**: 对话记录表可能会快速增长，建议定期清理旧数据或实施数据归档策略
2. **隐私保护**: 对话内容可能包含敏感信息，需要适当的访问控制
3. **存储优化**: 考虑对长文本内容进行压缩存储
4. **监控告警**: 建议对响应时间异常进行监控和告警

## 扩展功能

未来可以考虑添加：
- 对话内容的全文搜索
- 用户满意度评分
- 对话分类标签
- 导出功能
- 数据可视化仪表板

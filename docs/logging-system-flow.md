# 日志系统架构流程图

## 系统架构

```mermaid
graph TB
    A[应用启动] --> B[setup_logging()]
    B --> C[创建日志目录]
    C --> D[配置控制台输出]
    C --> E[配置文件输出]
    C --> F[配置错误日志]

    D --> G[彩色格式化输出]
    E --> H[app.log - 主日志]
    F --> I[error.log - 错误日志]

    H --> J[日志轮转 10MB]
    I --> K[日志轮转 10MB]
    J --> L[压缩存储 ZIP]
    K --> M[压缩存储 ZIP]

    N[定时任务调度器] --> O[每日凌晨2点]
    O --> P[cleanup_logs_task()]
    P --> Q[清理7天前日志]

    R[API请求] --> S[/logs/stats]
    R --> T[/logs/cleanup]
    R --> U[/logs/health]

    S --> V[获取日志统计]
    T --> W[手动清理日志]
    U --> X[健康检查]
```

## 日志文件结构

```
logs/
├── .gitkeep          # 保持目录结构
├── .gitignore        # 忽略日志文件
├── app.log           # 主日志文件
├── app.log.2025-01-27_12-00-00_123456.zip  # 轮转压缩文件
├── error.log         # 错误日志文件
└── error.log.2025-01-27_12-00-00_123456.zip  # 错误日志轮转文件
```

## 日志格式

### 控制台输出（彩色）
```
2025-01-27 12:00:00.123 | INFO     | app.main:lifespan:35 | 🚀 启动钉钉机器人服务
```

### 文件输出（纯文本）
```
2025-01-27 12:00:00.123 | INFO     | app.main:lifespan:35 | 🚀 启动钉钉机器人服务
```

## 功能特性

### 1. 自动轮转
- **触发条件**: 单个日志文件达到10MB
- **轮转方式**: 按时间戳命名，格式为 `{原文件名}.{时间戳}.zip`
- **压缩格式**: ZIP压缩，节省存储空间

### 2. 定期清理
- **清理策略**: 保留最近7天的日志文件
- **执行时间**: 每日凌晨2点自动执行
- **清理范围**: 所有 `.log*` 文件（包括压缩文件）

### 3. 分级记录
- **主日志**: 记录所有级别的日志信息
- **错误日志**: 单独记录ERROR级别日志
- **控制台**: 彩色格式化输出，便于开发调试

### 4. API管理
- **统计接口**: 获取日志文件数量、大小、时间范围等统计信息
- **清理接口**: 支持手动触发日志清理
- **健康检查**: 监控日志系统运行状态

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 日志目录 | `./logs` | 日志文件存储目录 |
| 轮转大小 | `10 MB` | 单个日志文件最大大小 |
| 保留天数 | `7 days` | 日志文件保留时间 |
| 压缩格式 | `zip` | 轮转文件压缩格式 |
| 日志级别 | `INFO` | 记录的最低日志级别 |

## 使用示例

### 1. 初始化日志系统
```python
from app.core.logger import setup_logging

# 在应用启动时调用
setup_logging()
```

### 2. 记录日志
```python
from loguru import logger

logger.info("应用启动成功")
logger.error("发生错误: {}", error_message)
logger.debug("调试信息: {}", debug_data)
```

### 3. 手动清理日志
```python
from app.core.logger import cleanup_logs

# 手动触发清理
cleanup_logs()
```

### 4. 获取日志统计
```python
from app.core.logger import get_log_stats

# 获取统计信息
stats = get_log_stats()
print(f"日志文件数量: {stats['total_files']}")
print(f"总大小: {stats['total_size']} bytes")
```
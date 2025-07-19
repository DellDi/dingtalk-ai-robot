# 开发环境使用指南

## 🚀 快速开始

### 开发模式（推荐）
```bash
# 启动开发服务器 - 自动检测热重载模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**特点**：
- ✅ 支持热重载，修改代码自动重启
- ✅ 智能检测，自动跳过钉钉客户端
- ✅ 完整的API功能
- ✅ 依赖注入容器正常工作

### 生产模式
```bash
# 启动完整服务
python -m app.main
```

**特点**：
- ✅ 完整功能，包含钉钉客户端
- ✅ 定时任务正常运行
- ✅ 适合生产环境部署

## 🔧 智能模式检测

系统会自动检测uvicorn的 `--reload` 参数来判断运行模式：

### 热重载模式
- **触发条件**：使用 `--reload` 参数启动
- **行为**：自动跳过钉钉客户端，避免热重载阻塞
- **日志**：`🔧 检测到热重载模式，钉钉客户端将在独立进程中运行`

### 生产模式
- **触发条件**：不使用 `--reload` 参数
- **行为**：启动完整服务，包含钉钉客户端
- **日志**：`🚀 生产模式，启动钉钉客户端`

### .env 文件示例
```bash
# 钉钉配置
DINGTALK_CLIENT_ID=your_client_id
DINGTALK_CLIENT_SECRET=your_client_secret

# 其他配置...
LOG_LEVEL=debug
```

## 📝 开发流程

### 1. 启动开发服务器
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 验证服务状态
```bash
# 检查服务状态
curl http://localhost:8000/demo/service-status

# 查看API文档
# 浏览器访问: http://localhost:8000/docs
```

### 3. 开发和测试
- 修改代码文件
- 服务自动重载
- 测试API功能

### 4. 测试完整功能（可选）
```bash
# 停止开发服务器 (Ctrl+C)
# 启动生产服务器
python -m app.main
```

## 🔄 热重载说明

### 支持的文件类型
- ✅ Python 文件 (`.py`)
- ✅ 配置文件修改
- ✅ 新增文件

### 排除的文件类型
- ❌ 编译文件 (`.pyc`, `.pyo`)
- ❌ 缓存目录 (`__pycache__`)
- ❌ 日志文件
- ❌ 数据文件

### 热重载日志示例
```
WARNING: WatchFiles detected changes in 'app\main.py'. Reloading...
INFO: Shutting down
🔄 开始关闭钉钉机器人服务
✅ 依赖注入容器清理完成
🎉 钉钉机器人服务关闭完成
INFO: Started server process [new_pid]
🚀 启动钉钉机器人服务
🔧 开发模式：跳过钉钉客户端和定时任务启动
✅ 所有服务启动完成
```

## 🧪 测试API

### 基础测试
```bash
# 健康检查
curl http://localhost:8000/health

# 服务状态
curl http://localhost:8000/demo/service-status

# 依赖注入信息
curl http://localhost:8000/demo/dependency-info
```

### 功能测试
```bash
# 周报生成（基于内容）
curl -X POST "http://localhost:8000/weekly-report/generate-summary" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "本周工作总结：完成了热重载功能优化",
    "use_quick_mode": true
  }'

# 知识库搜索
curl -X POST "http://localhost:8000/knowledge/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "依赖注入",
    "k": 3
  }'
```

## 🛠️ 故障排除

### 问题1：热重载失败
**症状**：修改文件后服务没有重启
**解决**：
```bash
# 检查是否使用开发脚本
python dev_server.py

# 检查文件是否在监控范围内
# 确保修改的是 app/ 目录下的文件
```

### 问题2：端口占用
**症状**：`Address already in use`
**解决**：
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8000
kill -9 <pid>
```

### 问题3：依赖注入错误
**症状**：服务启动失败，容器初始化错误
**解决**：
```bash
# 检查环境变量
echo $DEV_MODE

# 重新安装依赖
uv sync

# 清理缓存
rm -rf __pycache__
rm -rf .pytest_cache
```

### 问题4：API功能异常
**症状**：某些API返回错误
**解决**：
```bash
# 检查服务状态
curl http://localhost:8000/demo/service-status

# 查看日志
# 开发服务器会在控制台显示详细日志

# 如需完整功能，切换到生产模式
python prod_server.py
```

## 📊 模式对比

| 功能 | 开发模式 | 生产模式 |
|------|----------|----------|
| **热重载** | ✅ 支持 | ❌ 不支持 |
| **启动速度** | ✅ 快速 | ⚠️ 较慢 |
| **API功能** | ✅ 完整 | ✅ 完整 |
| **钉钉客户端** | ❌ 跳过 | ✅ 启动 |
| **定时任务** | ❌ 跳过 | ✅ 启动 |
| **依赖注入** | ✅ 正常 | ✅ 正常 |
| **适用场景** | 开发调试 | 生产部署 |

## 🎯 最佳实践

### 1. 开发工作流
```bash
# 1. 启动开发环境
python dev_server.py

# 2. 开发功能
# - 修改代码
# - 自动重载
# - 测试API

# 3. 完整测试
python prod_server.py

# 4. 部署
# 使用生产模式配置
```

### 2. 代码组织
- 将业务逻辑放在 `app/` 目录下
- 配置文件使用环境变量
- 测试文件放在 `tests/` 目录

### 3. 调试技巧
- 使用开发模式进行快速迭代
- 查看控制台日志了解详细信息
- 使用 `/demo/service-status` 检查服务状态

## 🎉 总结

现在您可以享受流畅的开发体验：

1. ✅ **快速启动**：开发模式下秒级启动
2. ✅ **热重载**：修改代码自动重启，无需手动操作
3. ✅ **完整功能**：API功能完全可用
4. ✅ **灵活切换**：开发和生产模式随时切换

开始您的开发之旅吧！🚀

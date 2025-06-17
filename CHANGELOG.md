# 更新日志

记录所有版本的重要变更。

## [1.2.1] - 2025-06-15
* **天气查询工具**: 支持中国区当天、小时、历史、七日等
* 兼容修复工具参数调用场景
## [1.2.0] - 2025-06-14

### 🚀 新特性
* **天气查询工具**: 集成OpenWeather One Call API 3.0，支持中国区当天和7天天气预报
  - 支持实时天气信息查询
  - 提供精美的Markdown格式天气展示
  - 异步HTTP请求优化性能

### 🔧 重构优化
* **AI工具模块化**: 完成AI工具架构重构，提升代码可维护性
  - 新建 `app/services/ai/tools/` 目录统一管理AI工具
  - 创建 `tools/__init__.py` 作为统一导出中心
  - 迁移天气、知识库、JIRA工具到独立模块
  - 保持 `handler.py` 薄包装层向后兼容

### 🛠️ 技术改进
* **配置管理**: 新增 `OPENWEATHER_API_KEY` 环境变量配置
* **循环导入修复**: 解决 `JiraTicketCreator` 循环导入问题
* **代码组织**: 优化导入结构，提升模块独立性

### 📚 文档更新
* **README**: 更新项目结构说明，新增AI工具模块化架构图
* **流程图**: 新增核心工具处理流程的mermaid图表

## [1.2.2] - 2025-06-17

### 🚀 新特性
* **知识库检索升级**
  - 支持请求参数 `min_score`，可动态调整相似度阈值
  - 实现 "超额取 + 二次重排" 流程：先按 `top_k × 3` 从向量库召回，再使用 DashScope `gte-rerank-v2` 对候选进行重排序
  - 返回结果结构中新增调试字段 `rerank_score`

### 🛠️ 技术改进
* **KnowledgeRetriever**
  - 去除初始化测试条目写入，防止噪声数据干扰召回
  - 增加阈值过滤、去重逻辑，以及超采上限配置
  - 在查询阶段集成 DashScope 重排，失败时自动降级

### 🔧 配置
* 新增环境变量 `DASHSCOPE_API_KEY`（若未配置则回退 `OPENAI_API_KEY`）

### 📚 文档
* 更新 `README.md`，补充 `/knowledge/search` 接口说明及重排流程

## [未发布] - 2025-06-13

### 📚 文档
* **README**: 新增 `/upload_document` 接口示例、切片参数说明，以及 AutoGen `multiple_system_messages` 配置注意事项。

### 🛠️ 变更
* 默认 `model_info` 增加 `multiple_system_messages=True`，兼容 SelectorGroupChat 多智能体多 system prompt 场景。

## [未发布] - 2025-06-09

### ✨ 新特性
-   **重构 `KnowledgeRetriever`**:
    -   通过 `aiohttp` 直接HTTP API调用集成了通义千问V4嵌入模型，移除了对嵌入功能的SDK依赖。
    -   利用AutoGen的 `ChromaDBVectorMemory` 进行持久化的本地向量存储。
    -   确保了初始化、文档添加、搜索和资源清理的完全异步操作。
    -   通过 `app.core.config.settings` 集中管理配置。
    -   修复了与协程处理和从 `ChromaDBVectorMemory` 解析数据相关的各种运行时错误。
    -   在 `app/services/knowledge/retriever.py` 中添加了详细的中文注释和示例用法。
    -   优化了 `TongyiQWenHttpEmbeddingFunction`，使其使用批量API调用，以提高嵌入多个文本时的效率。

## [0.1.0] - 2025-05-28

### 🎉 新增
* 初始项目结构设计和文档创建
* 基于钉钉官方示例代码的基础框架搭建
* 集成FastAPI作为后端服务框架
* 添加AutoGen多智能体支持
* 基本项目配置和依赖管理

### 🔧 优化
* 现代化Python项目结构
* 规范化代码风格和项目文档

### 🔄 计划
* 实现AI智能问答核心功能
* 建立知识库检索服务
* 开发JIRA任务管理模块
* 设计服务器远程管理功能

## [0.0.2] - 2025-06-03

### 🎉 新增
* 📝 将私有消息的默认类型更新为Markdown，支持更丰富的格式化内容
* 🤖 简化AI消息处理流程，直接传递文本内容至JIRA代理，提升数据处理效率
* 🆔 为JIRA代理流程新增对话ID，增强上下文关联性
* 🧹 移除独立的JiraBatchAgent文件，优化架构设计，统一JIRA处理逻辑至AIMessageHandler中

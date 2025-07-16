# 📊 周报管理系统架构流程图

## 🔄 完整工作流程

```mermaid
graph TB
    %% 定时任务触发
    A[每周六 20:30<br/>定时任务触发] --> B[WeeklyReportService<br/>自动周报任务]

    %% 日志收集阶段
    B --> C[检查用户日报记录]
    C --> D{钉钉API调用<br/>是否成功?}
    D -->|否| E[回退到本地示例数据]
    D -->|是| F[获取钉钉周一到周四日报]
    E --> G[整合日报内容]
    F --> G

    %% AI智能体处理阶段
    G --> H[WeeklyReportAgent<br/>AI智能体处理]
    H --> I{选择处理模式}
    I -->|标准模式| J[双智能体协作]
    I -->|快速模式| K[单智能体处理]

    %% 双智能体协作流程
    J --> L[总结智能体<br/>分析日志内容]
    L --> M[生成结构化周报]
    M --> N[检察官智能体<br/>审核总结质量]
    N --> O[确保专业性和准确性]
    O --> P[输出最终周报总结]

    %% 单智能体流程
    K --> Q[快速生成周报总结]
    Q --> P

    %% 钉钉推送阶段
    P --> R[DingTalkReportService<br/>钉钉日报服务]
    R --> S[格式化周报内容]
    S --> T[调用钉钉日报API]
    T --> U[创建钉钉日报]
    U --> V[发送到群聊]

    %% 数据持久化
    V --> W[保存AI总结后的周报<br/>到weekly_logs表]
    W --> X[任务执行完成]

    %% 状态通知
    X --> Y[发送成功通知<br/>到钉钉机器人]

    %% 异常处理
    C -.->|异常| Z[异常处理]
    H -.->|异常| Z
    R -.->|异常| Z
    Z --> AA[发送失败通知<br/>到钉钉机器人]

    %% 样式定义
    classDef processBox fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef aiBox fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef apiBox fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef dbBox fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef errorBox fill:#ffebee,stroke:#c62828,stroke-width:2px

    class A,B,C,X,Y processBox
    class H,I,J,K,L,M,N,O,P,Q aiBox
    class R,S,T,U,V apiBox
    class E,W dbBox
    class D,F,G apiBox
    class Z,AA errorBox
```

## 🏗️ 系统架构组件

```mermaid
graph LR
    %% 核心服务层
    subgraph "核心服务层"
        A[WeeklyReportService<br/>周报业务逻辑]
        B[DingTalkReportService<br/>钉钉API封装]
        C[WeeklyReportAgent<br/>AI智能体服务]
    end

    %% 数据层
    subgraph "数据持久层"
        D[(SQLite数据库<br/>weekly_logs表)]
        E[日志文件系统]
    end

    %% AI智能体层
    subgraph "AI智能体层"
        F[总结智能体<br/>SummarizerAgent]
        G[检察官智能体<br/>ReviewerAgent]
        H[AutoGen<br/>RoundRobinGroupChat]
    end

    %% 外部API层
    subgraph "外部API层"
        I[钉钉日报API]
        J[钉钉机器人API]
    end

    %% API接口层
    subgraph "API接口层"
        K[/api/weekly-report/check-dingding-logs]
        L[/api/weekly-report/generate-summary]
        M[/api/weekly-report/create-report]
        N[/api/weekly-report/auto-task]
    end

    %% 定时任务层
    subgraph "定时任务层"
        O[Scheduler调度器]
        P[每周六20:30<br/>定时触发]
    end

    %% 连接关系
    A --> D
    A --> C
    A --> B
    B --> I
    B --> J
    C --> F
    C --> G
    C --> H
    F --> H
    G --> H
    K --> A
    L --> A
    M --> A
    N --> A
    O --> P
    P --> A

    %% 样式定义
    classDef serviceBox fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef dataBox fill:#f1f8e9,stroke:#388e3c,stroke-width:2px
    classDef aiBox fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef apiBox fill:#fff8e1,stroke:#f57c00,stroke-width:2px
    classDef scheduleBox fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px

    class A,B,C serviceBox
    class D,E dataBox
    class F,G,H aiBox
    class I,J,K,L,M,N apiBox
    class O,P scheduleBox
```

## 📋 API接口调用流程

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant API as API接口
    participant Service as WeeklyReportService
    participant Agent as WeeklyReportAgent
    participant DingTalk as DingTalkReportService
    participant DB as 数据库

    %% 1. 检查日志接口
    Note over Client,DB: 1. 检查周报日志
    Client->>API: GET /api/weekly-report/check-logs
    API->>Service: check_user_weekly_logs()
    Service->>DingTalk: 查询钉钉周一到周四日报
    DingTalk-->>Service: 返回日报数据
    Service-->>API: 返回整合后的日志内容
    API-->>Client: JSON响应

    %% 2. 生成总结接口
    Note over Client,DB: 2. 生成周报总结
    Client->>API: POST /api/weekly-report/generate-summary
    API->>Service: generate_weekly_summary()
    Service->>Agent: 调用AI智能体
    Agent->>Agent: 双智能体协作处理
    Agent-->>Service: 返回周报总结
    Service-->>API: 返回总结结果
    API-->>Client: JSON响应

    %% 3. 创建报告接口
    Note over Client,DB: 3. 创建钉钉日报
    Client->>API: POST /api/weekly-report/create-report
    API->>Service: create_and_send_weekly_report()
    Service->>DingTalk: 格式化并创建日报
    DingTalk->>DingTalk: 调用钉钉API
    DingTalk-->>Service: 返回报告ID
    Service->>DB: 保存周报记录
    Service-->>API: 返回创建结果
    API-->>Client: JSON响应

    %% 4. 自动任务接口
    Note over Client,DB: 4. 执行自动任务
    Client->>API: POST /api/weekly-report/auto-task
    API->>Service: auto_weekly_report_task()
    Service->>Service: 执行完整流程
    Service->>Agent: AI生成总结
    Service->>DingTalk: 创建并发送日报
    Service->>DB: 保存所有数据
    Service-->>API: 返回任务结果
    API-->>Client: JSON响应
```

## 🎯 智能体协作机制

```mermaid
graph TD
    %% 输入阶段
    A[原始日志内容] --> B[WeeklyReportAgent]

    %% 模式选择
    B --> C{选择处理模式}

    %% 快速模式
    C -->|快速模式| D[单智能体处理]
    D --> E[SummarizerAgent<br/>快速生成总结]
    E --> F[输出周报总结]

    %% 标准模式
    C -->|标准模式| G[RoundRobinGroupChat<br/>双智能体协作]

    %% 双智能体协作流程
    G --> H[第一轮：SummarizerAgent]
    H --> I[分析日志内容<br/>生成初版周报]
    I --> J[第二轮：ReviewerAgent]
    J --> K[审核总结质量<br/>提出改进建议]
    K --> L{是否需要<br/>进一步优化?}
    L -->|是| M[第三轮：SummarizerAgent]
    M --> N[根据建议优化总结]
    N --> O[第四轮：ReviewerAgent]
    O --> P[最终审核确认]
    P --> F
    L -->|否| F

    %% 输出阶段
    F --> Q[专业化周报总结]
    Q --> R[发送到钉钉日报]

    %% 样式定义
    classDef inputBox fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef processBox fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef agentBox fill:#fce4ec,stroke:#ad1457,stroke-width:2px
    classDef outputBox fill:#fff3e0,stroke:#ef6c00,stroke-width:2px

    class A inputBox
    class B,C,G,L processBox
    class D,E,H,I,J,K,M,N,O,P agentBox
    class F,Q,R outputBox
```

## 🔧 配置和部署

### 环境变量配置

```bash
# 钉钉相关配置
DINGTALK_CLIENT_ID=your_client_id
DINGTALK_CLIENT_SECRET=your_client_secret
DINGTALK_ROBOT_CODE=your_robot_code

# AI模型配置
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key

# 数据库配置
DATABASE_PATH=./data/dingtalk_ai_robot.db
```

### 定时任务配置

系统默认配置每周六20:30执行周报生成任务，可在 `app/core/scheduler.py` 中修改：

```python
# 每周六20:30执行周报生成任务
schedule.every().saturday.at("20:30").do(lambda: asyncio.create_task(weekly_report_task()))
```

### 测试和验证

使用提供的测试脚本验证功能：

```bash
# 运行周报功能测试
uv run -m test_weekly_report

# 启动服务
uv run -m app.main

# 手动触发周报任务
curl -X POST http://localhost:8000/api/weekly-report/auto-task
```

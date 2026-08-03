# AI 应用开发学习路线

这份路线按项目的真实进度重排。

当前主线是：

```text
Python 基础
-> FastAPI
-> DeepSeek 调用
-> 聊天历史
-> SQLAlchemy
-> RAG
-> 后台任务
-> 生产化能力
```

这条主线更准确地说是“AI 应用后端地基”。它先解决接口、数据库、RAG、后台任务、部署等基础能力；真正的 Agent 会放在这条地基路线后面继续学习。

Go 仍然会学，但放在 Python AI 应用主线之后，作为后端服务能力补充。

## 已完成阶段

### 阶段 1：Python 最小基础

目标：能读懂简单脚本，并能做小范围修改。

已覆盖内容：

- 函数
- 字符串
- 列表
- 字典
- 文件读取
- JSON
- HTTP 请求
- 异常处理

对应模块：

- `examples/python/01_text_tool.py`
- `examples/python/02_http_json.py`

### 阶段 2：FastAPI Web API

目标：理解 Python 代码如何变成 HTTP 接口。

已覆盖内容：

- `uvicorn`
- `/docs`
- `GET`
- `POST`
- `PUT`
- `PATCH`
- `DELETE`
- 路径参数
- 查询参数
- 请求体
- `BaseModel`

对应模块：

- `examples/python/03_fastapi_app/main.py`
- `examples/python/04_fastapi_routes/main.py`

### 阶段 3：DeepSeek 聊天接口

目标：理解 AI 应用后端的最小分层。

已覆盖内容：

- `.env`
- `DEEPSEEK_API_KEY`
- mock 模式
- provider 层
- `system_prompt`
- `/chat`

对应模块：

- `examples/ai/01_chat_api`

### 阶段 4：聊天历史

目标：让一次性问答变成有状态聊天。

已覆盖内容：

- `sessions` 表
- `messages` 表
- `user` 消息
- `assistant` 消息
- 历史消息查询
- 带历史调用模型

对应模块：

- `examples/ai/02_chat_history`

### 阶段 5：SQLAlchemy 数据库版本

目标：从手写 SQL 过渡到 ORM。

已覆盖内容：

- SQLAlchemy
- ORM Model
- Pydantic Schema
- `Session`
- `DATABASE_URL`
- 简单统计接口
- 为 PostgreSQL 做准备

对应模块：

- `examples/ai/03_sqlalchemy_database`

### 阶段 6：RAG 文档问答

目标：理解 RAG 的最小链路。

已覆盖内容：

- 文档录入
- 文本切分
- chunk 存储
- 简单关键词检索
- sources 来源引用
- mock / DeepSeek 回答

对应模块：

- `examples/ai/04_rag_document_qa`

当前限制：

- 还没有 embedding。
- 还没有向量数据库。
- 检索方式只是关键词匹配。
- 有资料时模型仍可能说资料不足，后续会通过 prompt 设计、检索质量和上下文构造继续优化。

### 阶段 7：后台任务和状态查询

目标：理解耗时任务如何从同步接口拆出去。

已覆盖内容：

- 创建任务
- `task_id`
- `pending`
- `running`
- `succeeded`
- `failed`
- 后台 worker
- 状态查询

对应模块：

- `examples/ai/05_background_tasks`

## 后续阶段

### 阶段 8：PostgreSQL 实战

目标：从本地 SQLite 切到真正的 PostgreSQL。

要补的内容：

- 安装或连接 PostgreSQL
- 创建数据库
- 配置账号密码
- 使用 PostgreSQL `DATABASE_URL`
- 验证 SQLAlchemy 切换数据库
- 理解 SQLite 和 PostgreSQL 的差异

对应模块：

- `examples/ai/06_postgresql_setup`

### 阶段 9：Alembic 数据库迁移

目标：学会正式项目里如何管理表结构变化。

已覆盖内容：

- 初始化 Alembic
- 迁移文件结构
- 执行升级
- 执行回滚
- 给表新增字段
- 理解为什么不能生产环境直接 `create_all`

对应模块：

- `examples/ai/07_alembic_migrations`

### 阶段 10：向量化 RAG

目标：把关键词检索升级成 embedding 检索。

要补的内容：

- embedding 是什么
- 文本如何转向量
- 向量相似度
- 向量库
- chunk embedding 入库
- 查询 embedding
- top-k 向量检索

对应模块：

- `examples/ai/08_vector_rag`

### 阶段 11：流式输出

目标：让聊天接口像真实 AI 产品一样逐步返回内容。

已覆盖内容：

- 普通响应和流式响应的区别
- Server-Sent Events
- DeepSeek 流式返回
- 前端如何消费流式数据
- 错误中断处理

对应模块：

- `examples/ai/09_streaming_chat`

### 阶段 12：认证、限流和日志

目标：补齐 AI API 的基础安全和可观察性。

已覆盖内容：

- API Key 鉴权
- 请求日志
- 错误日志
- 模型调用日志
- 简单限流
- 统一错误响应
- 成本记录

对应模块：

- `examples/ai/10_auth_rate_limit_logging`

### 阶段 13：前端聊天页面

目标：把后端接口变成可使用的页面。

已覆盖内容：

- 最小聊天 UI
- 会话列表
- 消息历史
- 发送消息
- 任务状态轮询
- RAG sources 展示

对应模块：

- `examples/frontend/chat_ui`

### 阶段 14：Docker 和部署

目标：让项目可以在服务器上运行。

要补的内容：

- Dockerfile
- docker compose
- 环境变量
- PostgreSQL 容器
- 健康检查
- 生产启动命令

对应模块：

- `deploy/docker`

### 阶段 15：Go 后端补充

目标：理解 Go 在 AI 应用里的后端角色。

已覆盖内容：

- Go HTTP 服务
- 请求转发
- 简单网关
- 并发任务
- 调用 Python AI 服务
- Go 和 Python 的分工

对应已有基础示例：

- `examples/go/01_struct_and_slice.go`
- `examples/go/02_http_server.go`

对应模块：

- `examples/go/03_ai_gateway`

## Agent 进阶路线

前面的模块本身不等于 Agent。它们是 Agent 需要复用的地基：

- 聊天接口：模型入口。
- 聊天历史：短期上下文。
- 数据库：任务状态和记忆存储。
- RAG：知识检索工具。
- 后台任务：长任务执行能力。
- 流式输出：展示 Agent 执行过程。
- 认证、日志、部署：让 Agent 服务可以被真实使用。

完成 AI 应用后端地基后，再进入 Agent 正式学习路线。

Agent 路线不再只安排少量概念模块，而是按就业需要拆成完整工程主线：

```text
Agent 概念
-> 工具调用
-> Agent 循环
-> 提示词工程
-> 结构化输出
-> 上下文工程
-> 记忆工程
-> 工具工程
-> RAG 智能体
-> 数据库智能体
-> 后台任务智能体
-> 流式智能体
-> 运行基座工程
-> 可观测性
-> 评测
-> 安全
-> 测试
-> 成本、延迟和并发
-> 生产部署
-> 完整项目
```

根目录 `LEARNING_PLAN.md` 负责整个项目的总路线。Agent 方向因为模块很多，详细路线单独维护在：

- `examples/agent/AGENT_LEARNING_PLAN.md`

### 阶段 16：什么是 Agent

目标：先建立 Agent 的整体概念，知道它和普通聊天接口有什么区别。

已覆盖内容：

- Agent 是围绕目标做事的后端流程
- 普通聊天和 Agent 的区别
- 目标、思考、动作、观察、最终回答
- Agent 不等于大模型
- Agent 不等于工具调用
- 不依赖真实模型的最小 Agent 示例

对应模块：

- `examples/agent/00_what_is_agent`

### 阶段 17：工具调用

目标：让模型不只是回答，而是能选择调用工具。

已覆盖内容：

- 什么是工具
- 工具 schema
- 模型如何选择工具
- 工具参数从哪里来
- 工具调用结果如何返回给模型
- 工具调用失败如何处理
- mock 工具和真实工具的区别

对应模块：

- `examples/agent/01_tool_calling`

### 阶段 18：最小 Agent 循环

目标：理解 Agent 的核心循环。

要补的内容：

- user input
- model decision
- tool call
- observation
- final answer
- 最大循环次数
- 防止无限调用
- 中间步骤记录

对应模块：

- `examples/agent/02_minimal_agent_loop`

### 阶段 19：多工具编排

目标：理解一个用户目标如何拆成多个工具动作，并记录每一步输入、输出、耗时和错误。

已覆盖内容：

- 教学版 planner
- 多步骤执行计划
- 工具依赖关系
- 工具之间的数据传递
- 每个工具的输入、输出、耗时和错误记录
- 工具失败后的后续步骤跳过
- `stop_on_error` 对比

对应模块：

- `examples/agent/03_multi_tool_orchestration`

### 阶段 20：提示词工程

目标：把 prompt 当成可版本化、可测试、可回滚的工程资产。

已覆盖内容：

- system prompt 的职责
- prompt 独立文件管理
- prompt 版本列表和详情查看
- `.env` 中的 `PROMPT_VERSION`
- mock model 对比不同 prompt 行为
- 同一输入对比多个 prompt 版本
- prompt 改动对工具选择的影响

对应模块：

- `examples/agent/04_prompt_engineering`

### 阶段 21：结构化输出

目标：让模型输出变成后端能稳定解析和校验的数据结构。

已覆盖内容：

- 固定 JSON 输出契约
- JSON 解析和 Pydantic 校验分层
- 缺字段、字段类型错误、非法枚举值处理
- 输出不合法时重试一次
- 重试仍失败时返回人工审核降级结构
- mock / DeepSeek 双模式

对应模块：

- `examples/agent/05_structured_output`

### 阶段 22：上下文工程

目标：管理每次请求给模型看的 system prompt、用户问题、历史消息、RAG 结果和工具 observation。

已覆盖内容：

- `build_context()` 教学版上下文构造。
- system prompt、当前问题、历史消息、RAG source、工具 observation 分层。
- 历史消息按预算裁剪。
- RAG 资料按相关性过滤。
- 工具 observation 注入上下文。
- `/context/preview` 预览模型真实输入。
- 对比低相关 RAG 干扰回答。
- mock / DeepSeek 双模式。

对应模块：

- `examples/agent/06_context_engineering`

### 阶段 23：短期状态管理

目标：保存 Agent 当前 run、steps 和中间状态，支持查询和恢复。

对应未来模块：

- `examples/agent/07_short_term_state`

### 阶段 24：Agent 记忆基础

目标：区分聊天历史和长期记忆，学习记忆写入、检索和复用。

对应未来模块：

- `examples/agent/08_memory_basics`

### 阶段 25：记忆治理

目标：学习记忆删除、过期、更新和敏感信息拒绝写入。

对应未来模块：

- `examples/agent/09_memory_governance`

### 阶段 26：工具设计和权限

目标：学习工具注册表、工具权限、读写工具边界和用户级授权。

对应未来模块：

- `examples/agent/10_tool_permissions`

### 阶段 27：危险操作和人工确认

目标：学习删除、付款、发邮件、写数据库前的人工确认流程。

对应未来模块：

- `examples/agent/11_human_confirmation`

### 阶段 28：工具失败和恢复策略

目标：学习工具超时、重试、降级和失败解释。

对应未来模块：

- `examples/agent/12_tool_failure_recovery`

### 阶段 29：RAG 工具智能体

目标：把前面学过的 RAG 变成 Agent 可以主动调用的工具。

对应未来模块：

- `examples/agent/13_rag_tool_agent`

### 阶段 30：生产级 RAG 工程

目标：学习真实文档处理、metadata、权限隔离、rerank 和 RAG 评测前置数据。

对应未来模块：

- `examples/agent/14_production_rag`

### 阶段 31：数据库工具智能体

目标：让 Agent 查询和修改结构化数据，并记录所有操作。

对应未来模块：

- `examples/agent/15_database_tool_agent`

### 阶段 32：后台任务智能体

目标：让 Agent 发起耗时任务并查询进度。

对应未来模块：

- `examples/agent/16_background_task_agent`

### 阶段 33：流式智能体输出

目标：把 Agent 执行过程实时展示给前端。

对应未来模块：

- `examples/agent/17_streaming_agent_events`

### 阶段 34：Agent 前端工作台

目标：做一个能查看会话、任务、工具调用和 sources 的工作台。

对应未来模块：

- `examples/agent/18_agent_workspace_ui`

### 阶段 35：Agent 运行基座工程

目标：搭建一个可批量运行、可复现、可回放、可接入评测的 Agent 运行基座。这个能力也常被叫做 harness。

要补的内容：

- 测试样例集
- 固定输入和期望行为
- mock 模型
- mock 工具
- 批量运行 Agent
- 保存每次运行的输入、输出、steps 和工具结果
- 支持失败样例回放
- 为后续评测和测试提供统一入口

对应未来模块：

- `examples/agent/19_agent_harness`

### 阶段 36：Agent Trace 和日志

目标：让 Agent 每一步可追踪、可调试、可复盘。

对应未来模块：

- `examples/agent/20_agent_observability`

### 阶段 37：Agent 评测

目标：学习如何证明 Agent 改动真的变好。

对应未来模块：

- `examples/agent/21_agent_evals`

### 阶段 38：Agent 安全

目标：防 prompt injection、敏感信息泄露、越权工具调用和危险写操作。

对应未来模块：

- `examples/agent/22_agent_safety`

### 阶段 39：Agent 测试

目标：用单元测试、接口测试、工具 mock、模型 mock 和测试数据库保护 Agent 项目。

对应未来模块：

- `examples/agent/23_agent_testing`

### 阶段 40：成本、延迟和并发

目标：控制 token 成本、响应延迟和并发风险。

对应未来模块：

- `examples/agent/24_cost_latency_concurrency`

### 阶段 41：Agent 生产部署

目标：把 Agent 服务按生产方式部署。

对应未来模块：

- `deploy/agent_production`

### 阶段 42：完整项目一：企业知识库 Agent

目标：做一个可展示的 RAG 智能体作品。

对应未来模块：

- `projects/agent_knowledge_base`

### 阶段 43：完整项目二：业务操作 Agent

目标：做一个能查询、创建任务、修改结构化数据的业务 Agent。

对应未来模块：

- `projects/agent_business_assistant`

### 阶段 44：简历和面试复盘

目标：把学习成果整理成能面试的作品材料。

对应未来模块：

- `career/agent_engineer_portfolio`

## 练习设计原则

后续练习必须有真实学习价值。

应该优先设计这些练习：

- 能暴露真实工程问题。
- 能观察状态变化。
- 能理解完整链路。
- 能练习异常处理。
- 能做小型设计判断。

避免这些练习：

- 单纯改数字。
- 单纯复制同类接口。
- 单纯改返回文案。
- 与当前模块目标高度同质化的任务。

## 当前推荐下一步

如果你已经完成 `examples/agent/05_structured_output`，下一步应该进入：

```text
上下文工程
```

入口：

- `examples/agent/06_context_engineering`

原因是你已经理解了 prompt 如何影响 Agent 行为，也理解了模型输出必须变成后端可解析、可校验、可降级的数据结构。下一步要学习每次模型调用到底应该看到哪些上下文：system prompt、用户问题、历史消息、RAG 结果和工具 observation。

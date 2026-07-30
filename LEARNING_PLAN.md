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

要补的内容：

- 普通响应和流式响应的区别
- Server-Sent Events
- DeepSeek 流式返回
- 前端如何消费流式数据
- 错误中断处理

对应未来模块：

- `examples/ai/09_streaming_chat`

### 阶段 12：认证、限流和日志

目标：补齐 AI API 的基础安全和可观察性。

要补的内容：

- API Key 鉴权
- 请求日志
- 错误日志
- 模型调用日志
- 简单限流
- 统一错误响应
- 成本记录

对应未来模块：

- `examples/ai/10_auth_rate_limit_logging`

### 阶段 13：前端聊天页面

目标：把后端接口变成可使用的页面。

要补的内容：

- 最小聊天 UI
- 会话列表
- 消息历史
- 发送消息
- 任务状态轮询
- RAG sources 展示

对应未来模块：

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

对应未来模块：

- `deploy/docker`

### 阶段 15：Go 后端补充

目标：理解 Go 在 AI 应用里的后端角色。

要补的内容：

- Go HTTP 服务
- 请求转发
- 简单网关
- 并发任务
- 调用 Python AI 服务
- Go 和 Python 的分工

对应已有基础示例：

- `examples/go/01_struct_and_slice.go`
- `examples/go/02_http_server.go`

未来可扩展模块：

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

完成 AI 应用后端地基后，再进入 Agent 进阶。

### 阶段 16：工具调用 Tool Calling

目标：让模型不只是回答，而是能选择调用工具。

要补的内容：

- 什么是工具
- 工具 schema
- 模型如何选择工具
- 工具参数从哪里来
- 工具调用结果如何返回给模型
- 工具调用失败如何处理
- mock 工具和真实工具的区别

对应未来模块：

- `examples/agent/01_tool_calling`

### 阶段 17：最小 Agent Loop

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

对应未来模块：

- `examples/agent/02_minimal_agent_loop`

### 阶段 18：带 RAG 工具的 Agent

目标：把前面学过的 RAG 变成 Agent 可以主动调用的工具。

要补的内容：

- `search_documents` 工具
- Agent 何时应该检索资料
- sources 如何进入最终回答
- 检索不到资料时如何追问或说明不足
- RAG 工具和普通聊天的边界

对应未来模块：

- `examples/agent/03_rag_tool_agent`

### 阶段 19：带数据库操作的 Agent

目标：让 Agent 能读取和修改结构化数据。

要补的内容：

- 查询工具
- 写入工具
- 参数校验
- 用户确认
- 防止危险写操作
- 操作日志

对应未来模块：

- `examples/agent/04_database_tool_agent`

### 阶段 20：带后台任务的 Agent

目标：让 Agent 能发起耗时任务，并查询任务进度。

要补的内容：

- 创建任务工具
- 查询任务状态工具
- `pending` / `running` / `succeeded` / `failed`
- Agent 如何根据状态决定下一步
- 任务失败后的恢复策略

对应未来模块：

- `examples/agent/05_background_task_agent`

### 阶段 21：Agent 记忆

目标：理解 Agent 如何保存和复用长期信息。

要补的内容：

- 短期上下文和长期记忆的区别
- 记忆写入策略
- 记忆检索
- 用户偏好保存
- 过期和删除
- 隐私边界

对应未来模块：

- `examples/agent/06_agent_memory`

### 阶段 22：Agent 可观测性和安全

目标：让 Agent 的每一步可追踪、可调试、可限制。

要补的内容：

- tool call 日志
- 中间步骤 trace
- 错误记录
- 成本记录
- 工具权限
- 人工确认
- 最大执行时间

对应未来模块：

- `examples/agent/07_agent_observability_safety`

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

如果你已经完成 `07_alembic_migrations`，下一步应该进入：

```text
向量化 RAG
```

原因是你已经学过关键词版 RAG、PostgreSQL 和 Alembic。下一步要把 RAG 的检索部分从关键词匹配升级成 embedding 相似度检索，理解 chunk embedding 入库、查询 embedding、top-k 检索和相似度阈值。

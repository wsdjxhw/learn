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

对应未来模块：

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

如果你已经完成 `06_postgresql_setup`，下一步应该进入：

```text
Alembic 数据库迁移
```

原因是你已经能把 SQLAlchemy 从 SQLite 切到 PostgreSQL。下一步要学会用版本化迁移管理表结构变化，而不是依赖 `create_all`。

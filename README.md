# AI 应用开发入门学习项目

这是一个面向初学者的 AI 应用开发学习项目。

项目目标不是一开始就学习复杂 Agent 框架或模型训练，而是用一组可以运行、可以修改、带详细注释的示例，逐步理解一个 AI 应用后端是怎么搭起来的。

当前路线以 `Python + FastAPI + DeepSeek + SQLite/SQLAlchemy` 为主。Go 会作为后续后端补充方向，不作为当前主线。

当前主线先打 AI 应用后端地基；Agent 相关内容会放在这条地基路线之后继续学习。

## 适合谁

- Python 语法还不熟，但想做 AI 应用。
- 学过 Java，想用类比方式理解 Python 后端。
- 想从脚本、接口、数据库、RAG、后台任务一步步学起。
- 想把这个仓库作为自己的 AI 应用开发入门项目。

## 当前真实进度

已经完成并进入学习路线的模块：

1. Python 文本处理
2. HTTP 和 JSON
3. FastAPI 最小接口
4. FastAPI 常见接口类型
5. DeepSeek 聊天接口
6. 带聊天历史的聊天接口
7. SQLAlchemy 数据库版本
8. RAG 文档问答
9. 后台任务和状态查询
10. PostgreSQL 实战连接
11. Alembic 数据库迁移
12. 向量化 RAG 框架
13. 流式聊天接口

当前还没有正式展开的模块：

- 认证、限流和日志
- 前端聊天页面
- Docker 部署
- Go 后端补充
- Agent 工具调用和 Agent Loop

## 从哪里开始

第一次学习先看：

[START_HERE.md](START_HERE.md)

如果你已经学过前面的基础模块，可以直接进入当前 AI 主线：

[examples/ai](examples/ai)

## 推荐学习顺序

### 1. Python 文本处理

代码：

[examples/python/01_text_tool.py](examples/python/01_text_tool.py)

讲解：

[examples/python/01_text_tool_EXPLAINED.md](examples/python/01_text_tool_EXPLAINED.md)

学习目标：

- 理解函数
- 理解字符串、列表、字典
- 理解 `main()` 程序入口
- 能修改返回字段

### 2. HTTP 和 JSON

代码：

[examples/python/02_http_json.py](examples/python/02_http_json.py)

讲解：

[examples/python/02_http_json_EXPLAINED.md](examples/python/02_http_json_EXPLAINED.md)

学习目标：

- 理解 HTTP 请求
- 理解 JSON
- 理解列表和字典的数据处理
- 理解网络异常处理

### 3. FastAPI 最小接口

代码：

[examples/python/03_fastapi_app/main.py](examples/python/03_fastapi_app/main.py)

学习目标：

- 启动 FastAPI 服务
- 打开 `/docs`
- 理解 `GET /health`
- 理解 `POST /echo`
- 理解 `BaseModel` 类似 Java 请求 DTO

### 4. FastAPI 常见接口类型

代码：

[examples/python/04_fastapi_routes/main.py](examples/python/04_fastapi_routes/main.py)

说明：

[examples/python/04_fastapi_routes/README.md](examples/python/04_fastapi_routes/README.md)

学习目标：

- 理解 `GET`、`POST`、`PUT`、`PATCH`、`DELETE`
- 理解路径参数
- 理解查询参数
- 理解请求体

### 5. DeepSeek 聊天接口

代码：

[examples/ai/01_chat_api/main.py](examples/ai/01_chat_api/main.py)

讲解：

[examples/ai/01_chat_api/AI_CHAT_API_EXPLAINED.md](examples/ai/01_chat_api/AI_CHAT_API_EXPLAINED.md)

学习目标：

- 理解接口层和 provider 层分离
- 理解 `.env`
- 理解 mock 模式
- 理解 DeepSeek API 调用

### 6. 带聊天历史的接口

代码：

[examples/ai/02_chat_history/main.py](examples/ai/02_chat_history/main.py)

讲解：

[examples/ai/02_chat_history/CHAT_HISTORY_EXPLAINED.md](examples/ai/02_chat_history/CHAT_HISTORY_EXPLAINED.md)

学习目标：

- 理解会话表和消息表
- 保存用户消息
- 保存 AI 回复
- 查询历史消息
- 把历史消息传给模型

### 7. SQLAlchemy 数据库版本

代码：

[examples/ai/03_sqlalchemy_database/main.py](examples/ai/03_sqlalchemy_database/main.py)

讲解：

[examples/ai/03_sqlalchemy_database/SQLALCHEMY_EXPLAINED.md](examples/ai/03_sqlalchemy_database/SQLALCHEMY_EXPLAINED.md)

学习目标：

- 理解 ORM
- 理解 Entity 和 DTO 的区别
- 理解 `Session`
- 理解 `DATABASE_URL`
- 为 PostgreSQL 和 Alembic 做准备

### 8. RAG 文档问答

代码：

[examples/ai/04_rag_document_qa/main.py](examples/ai/04_rag_document_qa/main.py)

讲解：

[examples/ai/04_rag_document_qa/RAG_EXPLAINED.md](examples/ai/04_rag_document_qa/RAG_EXPLAINED.md)

学习目标：

- 理解文档切分
- 理解 chunk
- 理解检索
- 理解 sources 来源引用
- 理解 RAG 基本链路

### 9. 后台任务和状态查询

代码：

[examples/ai/05_background_tasks/main.py](examples/ai/05_background_tasks/main.py)

讲解：

[examples/ai/05_background_tasks/BACKGROUND_TASKS_EXPLAINED.md](examples/ai/05_background_tasks/BACKGROUND_TASKS_EXPLAINED.md)

学习目标：

- 理解耗时任务为什么不能阻塞接口
- 理解 `task_id`
- 理解 `pending`、`running`、`succeeded`、`failed`
- 理解后台 worker
- 理解状态查询接口

### 10. PostgreSQL 实战连接

代码：

[examples/ai/06_postgresql_setup/main.py](examples/ai/06_postgresql_setup/main.py)

讲解：

[examples/ai/06_postgresql_setup/POSTGRESQL_EXPLAINED.md](examples/ai/06_postgresql_setup/POSTGRESQL_EXPLAINED.md)

学习目标：

- 理解 `DATABASE_URL`
- 理解 SQLite 和 PostgreSQL 连接差异
- 理解数据库健康检查
- 验证 SQLAlchemy 切换数据库
- 为 Alembic 数据库迁移做准备

### 11. Alembic 数据库迁移

代码：

[examples/ai/07_alembic_migrations/main.py](examples/ai/07_alembic_migrations/main.py)

讲解：

[examples/ai/07_alembic_migrations/ALEMBIC_EXPLAINED.md](examples/ai/07_alembic_migrations/ALEMBIC_EXPLAINED.md)

学习目标：

- 理解 `create_all` 的限制
- 理解 Alembic revision、head、upgrade、downgrade
- 执行数据库结构升级和回滚
- 观察代码版本和数据库版本不匹配的问题
- 理解已有数据下新增非空字段的风险

### 12. 向量化 RAG

代码：

[examples/ai/08_vector_rag/main.py](examples/ai/08_vector_rag/main.py)

讲解：

[examples/ai/08_vector_rag/VECTOR_RAG_EXPLAINED.md](examples/ai/08_vector_rag/VECTOR_RAG_EXPLAINED.md)

学习目标：

- 理解 embedding 是什么
- 理解 chunk embedding 入库
- 理解查询 embedding
- 理解 cosine similarity
- 理解 `top_k` 和 `min_score`
- 理解教学版 mock embedding 和真实向量库的差异

### 13. 流式聊天接口

代码：

[examples/ai/09_streaming_chat/main.py](examples/ai/09_streaming_chat/main.py)

讲解：

[examples/ai/09_streaming_chat/STREAMING_CHAT_EXPLAINED.md](examples/ai/09_streaming_chat/STREAMING_CHAT_EXPLAINED.md)

学习目标：

- 理解普通 JSON 响应和流式响应的区别
- 理解 Server-Sent Events
- 理解 `StreamingResponse`
- 理解 `yield` 和生成器
- 理解浏览器 `EventSource`
- 理解流式错误处理

## FastAPI 示例怎么启动

进入具体模块目录：

```powershell
cd examples\ai\05_background_tasks
```

启动：

```powershell
python -m uvicorn main:app --reload
```

打开：

```text
http://127.0.0.1:8000/docs
```

如果端口被占用：

```powershell
python -m uvicorn main:app --reload --port 9000
```

## DeepSeek 配置

AI 模块都提供 `.env.example`。

本地 `.env` 示例：

```text
DEEPSEEK_API_KEY=put-your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-v4-flash
```

没有真实 key 时，会走 mock 模式。mock 模式用于学习接口流程，不调用真实模型。

## 文档和代码要求

这个仓库面向 Python 初学者，所以代码必须保留中文教学注释。

每个模块的练习必须有实际学习价值，避免只做机械改数字、复制同类接口、只改返回文案这类低质量任务。

## 长期路线

完整后续计划看：

[LEARNING_PLAN.md](LEARNING_PLAN.md)

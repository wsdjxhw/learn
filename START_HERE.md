# 从这里开始

这个项目已经按真实学习进度重排。

如果你是第一次打开仓库，不要直接看最新模块。按下面顺序学习。

## 第 1 步：Python 基础

先看：

[examples/python/01_text_tool.py](examples/python/01_text_tool.py)

再看：

[examples/python/01_text_tool_EXPLAINED.md](examples/python/01_text_tool_EXPLAINED.md)

目标：

- 跑通脚本
- 看懂输入、处理、输出
- 改一个返回字段
- 自己重写一个简化版

## 第 2 步：HTTP 和 JSON

看：

[examples/python/02_http_json.py](examples/python/02_http_json.py)

讲解：

[examples/python/02_http_json_EXPLAINED.md](examples/python/02_http_json_EXPLAINED.md)

目标：

- 理解请求 API
- 理解 JSON
- 理解列表和字典

## 第 3 步：FastAPI

先看：

[examples/python/03_fastapi_app/main.py](examples/python/03_fastapi_app/main.py)

再看：

[examples/python/04_fastapi_routes/main.py](examples/python/04_fastapi_routes/main.py)

目标：

- 启动服务
- 打开 `/docs`
- 理解常见接口类型
- 理解参数来源

## 第 4 步：AI 应用主线

按顺序学习：

1. [DeepSeek 聊天接口](examples/ai/01_chat_api/README.md)
2. [带聊天历史的接口](examples/ai/02_chat_history/README.md)
3. [SQLAlchemy 数据库版本](examples/ai/03_sqlalchemy_database/README.md)
4. [RAG 文档问答](examples/ai/04_rag_document_qa/README.md)
5. [后台任务和状态查询](examples/ai/05_background_tasks/README.md)
6. [PostgreSQL 实战连接](examples/ai/06_postgresql_setup/README.md)
7. [Alembic 数据库迁移](examples/ai/07_alembic_migrations/README.md)
8. [向量化 RAG](examples/ai/08_vector_rag/README.md)
9. [流式聊天接口](examples/ai/09_streaming_chat/README.md)
10. [认证、限流和日志](examples/ai/10_auth_rate_limit_logging/README.md)
11. [前端聊天页面](examples/frontend/chat_ui/README.md)
12. [Docker 和部署](deploy/docker/README.md)
13. [Go AI 网关](examples/go/03_ai_gateway/README.md)
14. [什么是 Agent](examples/agent/00_what_is_agent/README.md)
15. [Agent 工具调用](examples/agent/01_tool_calling/README.md)
16. [最小 Agent 循环](examples/agent/02_minimal_agent_loop/README.md)
17. [多工具编排](examples/agent/03_multi_tool_orchestration/README.md)
18. [提示词工程](examples/agent/04_prompt_engineering/README.md)
19. [结构化输出](examples/agent/05_structured_output/README.md)
20. [上下文工程](examples/agent/06_context_engineering/README.md)

## 每个模块怎么学

每个模块都按这个顺序：

1. 先读模块自己的 `README.md`。
2. 启动服务。
3. 打开 `http://127.0.0.1:8000/docs`。
4. 按 README 的接口顺序测试。
5. 再读 `*_EXPLAINED.md`。
6. 最后做练习。

## 当前路线

完整路线看：

[LEARNING_PLAN.md](LEARNING_PLAN.md)

说明：当前主线先学习 AI 应用后端地基，Go 作为后端服务能力补充。现在已经开始进入 Agent 正式路线，先学习什么是 Agent，再学习工具调用，后续会继续展开 Agent 循环、提示词工程、上下文工程、记忆工程、RAG 智能体、运行基座工程、评测、安全、部署和完整项目。

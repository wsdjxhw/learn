# AI 应用开发入门学习项目

这是一个从零开始学习 AI 应用开发的开源入门项目。

项目目标不是一次性学完所有技术，而是用一条尽量短、可运行、能持续扩展的路线，带你从 Python 基础脚本走到一个带历史记录的 AI 聊天接口。

## 适合谁

适合这些学习者：

- 会一点编程，想入门 AI 应用开发。
- 学过 Java，想迁移到 Python / FastAPI。
- 想知道 AI 应用后端到底由哪些部分组成。
- 不想一开始就陷入复杂 Agent 框架、模型训练、微服务和部署细节。

## 你会学到什么

这套项目当前覆盖：

- Python 基础脚本
- HTTP 和 JSON
- FastAPI Web API
- 常见接口类型：`GET`、`POST`、`PUT`、`PATCH`、`DELETE`
- 请求参数：路径参数、查询参数、请求体
- AI 聊天接口
- DeepSeek API 配置
- `.env` 本地配置文件
- mock 模式
- SQLite 保存聊天历史
- 会话表和消息表的基本设计

## 从哪里开始

第一步只看：

[START_HERE.md](START_HERE.md)

不要一开始就把整个项目都看完。按下面顺序来。

## 学习顺序

### 1. Python 文本处理

先学这个：

[examples/python/01_text_tool.py](examples/python/01_text_tool.py)

配套讲解：

[examples/python/01_text_tool_EXPLAINED.md](examples/python/01_text_tool_EXPLAINED.md)

目标：

- 看懂函数
- 看懂 `main()`
- 看懂字符串、列表、字典
- 能自己修改返回字段

### 2. HTTP 和 JSON

代码：

[examples/python/02_http_json.py](examples/python/02_http_json.py)

配套讲解：

[examples/python/02_http_json_EXPLAINED.md](examples/python/02_http_json_EXPLAINED.md)

目标：

- 知道什么是 HTTP 请求
- 知道什么是 JSON
- 知道 JSON 如何变成 Python 数据
- 能遍历列表和字典

### 3. FastAPI 最小接口

代码：

[examples/python/03_fastapi_app/main.py](examples/python/03_fastapi_app/main.py)

目标：

- 启动 FastAPI 服务
- 打开 `/docs`
- 看懂 `GET /health`
- 看懂 `POST /echo`
- 理解 `BaseModel` 类似 Java 里的请求 DTO

### 4. FastAPI 常见接口类型

代码：

[examples/python/04_fastapi_routes/main.py](examples/python/04_fastapi_routes/main.py)

说明：

[examples/python/04_fastapi_routes/README.md](examples/python/04_fastapi_routes/README.md)

目标：

- 理解 `GET`、`POST`、`PUT`、`PATCH`、`DELETE`
- 理解路径参数
- 理解查询参数
- 理解请求体

### 5. 最小 DeepSeek 聊天接口

代码：

[examples/ai/01_chat_api/main.py](examples/ai/01_chat_api/main.py)

模型调用层：

[examples/ai/01_chat_api/provider.py](examples/ai/01_chat_api/provider.py)

讲解：

[examples/ai/01_chat_api/AI_CHAT_API_EXPLAINED.md](examples/ai/01_chat_api/AI_CHAT_API_EXPLAINED.md)

目标：

- 理解接口层和模型调用层分离
- 理解 `.env` 配置
- 理解 mock 模式
- 理解 DeepSeek API 调用流程

### 6. 带聊天历史的 AI 接口

代码：

[examples/ai/02_chat_history/main.py](examples/ai/02_chat_history/main.py)

数据库层：

[examples/ai/02_chat_history/db.py](examples/ai/02_chat_history/db.py)

讲解：

[examples/ai/02_chat_history/CHAT_HISTORY_EXPLAINED.md](examples/ai/02_chat_history/CHAT_HISTORY_EXPLAINED.md)

目标：

- 创建会话
- 保存用户消息
- 保存 AI 回复
- 查询历史消息
- 理解 SQLite 在学习阶段的作用

## 启动 FastAPI 示例

进入对应目录后运行：

```powershell
python -m uvicorn main:app --reload
```

默认访问地址：

```text
http://127.0.0.1:8000/docs
```

如果端口被占用，可以换端口：

```powershell
python -m uvicorn main:app --reload --port 9000
```

## 配置 DeepSeek

AI 示例目录里有 `.env` 文件：

```text
DEEPSEEK_API_KEY=put-your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-v4-flash
```

如果没有真实 key，会自动走 mock 模式。

如果要调用真实 DeepSeek，把第一行改成你的 key。

## 为什么先用 SQLite

学习阶段先用 SQLite，因为它不需要安装数据库服务，也不需要配置账号密码。

真正要学的是这条链路：

```text
会话 -> 用户消息 -> AI 回复 -> 历史记录
```

后面可以再把 SQLite 换成 PostgreSQL。

## 大路线

完整方向看：

[LEARNING_PLAN.md](LEARNING_PLAN.md)

已经学到某一步卡住时，不要跳到后面。先把当前文件跑通、改动一次、再自己重写一遍。

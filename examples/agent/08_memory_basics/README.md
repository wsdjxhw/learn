# Agent 记忆基础 Memory Basics

这个模块是 Agent 进阶路线的第九步。

你已经学完短期状态管理，知道一次 Agent run 的 `status`、`steps`、中间输入输出和失败现场应该保存下来。现在进入长期记忆：Agent 如何记住“未来还会有价值”的用户信息，并在后续请求中复用。

长期记忆不是聊天历史的同义词。聊天历史保存原始对话，长期记忆保存筛选、压缩、结构化后的信息，例如用户偏好、用户背景、长期指令。

本模块默认使用 mock 模式，不需要 API Key。配置 `MODEL_MODE=deepseek` 后，也可以用 `openai` Python 包的 OpenAI 兼容协议调用 DeepSeek。

## 学习目标

- 区分聊天历史、短期状态和长期记忆。
- 理解为什么不能把所有聊天记录都当成记忆。
- 学会从用户输入中提取结构化 memory candidate。
- 学会用 SQLite + SQLAlchemy 保存 `user_memories`。
- 学会按 `user_id` 隔离记忆，避免不同用户互相污染。
- 学会在后续请求中检索相关 memory，并放进模型上下文。
- 理解记忆写入需要保守，后续模块再学习删除、过期、敏感信息治理。

## 文件结构

```text
examples/agent/08_memory_basics
├── main.py
├── settings.py
├── database.py
├── models.py
├── schemas.py
├── memory_extractor.py
├── memory_store.py
├── context_builder.py
├── provider.py
├── MEMORY_BASICS.md
├── MEMORY_BASICS_EXPLAINED.md
├── START_HERE.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `settings.py`：读取 `.env` 配置，决定 mock / DeepSeek / 数据库地址。
- `database.py`：SQLAlchemy 引擎、Session 和依赖注入。
- `models.py`：ORM Model，定义聊天历史、长期记忆、记忆使用日志。
- `schemas.py`：请求 DTO 和响应 DTO。
- `memory_extractor.py`：从用户输入里提取候选记忆。
- `memory_store.py`：长期记忆的保存、更新、查询、检索。
- `context_builder.py`：把检索到的记忆转换成模型可读上下文。
- `provider.py`：模型调用层，默认 mock，也支持 DeepSeek。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\08_memory_basics
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置模板：

```powershell
Copy-Item .env.example .env
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口页面：

```text
http://127.0.0.1:8000/docs
```

## 接口测试顺序

### 1. 查看健康状态

测试：

```text
GET /health
```

重点看：

- `module` 是否是 `08_memory_basics`。
- `model_mode` 默认是否是 `mock`。
- `database_url` 是否指向 `sqlite:///./agent_memory.db`。

### 2. 预览记忆提取

测试：

```text
POST /memory/extract
```

请求体：

```json
{
  "text": "我是 AI 应用初学者，以后请用中文回答，我喜欢就业级、企业级的讲解。"
}
```

你会看到候选记忆，例如：

- `reply_language = 中文`
- `learning_level = 初学者`
- `learning_goal = 偏向就业级、企业级内容`

这个接口不写数据库，只帮助你观察提取规则。

### 3. 第一次聊天并写入记忆

测试：

```text
POST /agent/chat
```

请求体：

```json
{
  "user_id": "u_001",
  "message": "我是 AI 应用初学者，以后请用中文回答，我喜欢就业级、企业级的讲解。"
}
```

重点看：

- `extracted_memories`：本轮从用户输入提取出的候选记忆。
- `saved_memory_count`：写入或更新了几条长期记忆。
- `used_memories`：本轮回答实际使用了哪些记忆。
- `message_count`：聊天历史消息数量。

### 4. 查看用户长期记忆

测试：

```text
GET /users/u_001/memories
```

你应该能看到刚才保存的结构化记忆。

这里要注意：表里保存的不是完整聊天原文，而是 `memory_type`、`key`、`value`、`source_text`、`confidence` 这样的结构。

### 5. 后续请求复用记忆

测试：

```text
POST /agent/chat
```

请求体：

```json
{
  "user_id": "u_001",
  "message": "帮我规划下一步 Agent 学习内容。"
}
```

重点看 `used_memories`。

如果前面保存成功，这次即使用户没有重复说“我是初学者、偏就业级”，Agent 也能检索并复用这些长期记忆。

### 6. 验证用户隔离

测试：

```text
POST /agent/chat
```

请求体：

```json
{
  "user_id": "u_002",
  "message": "帮我规划下一步 Agent 学习内容。"
}
```

`u_002` 不应该拿到 `u_001` 的记忆。

这是企业级 Agent 必须重视的边界：长期记忆一旦跨用户污染，就会变成隐私和安全问题。

## 练习任务

### 练习一：新增一个高价值记忆规则

在 `memory_extractor.py` 里新增规则：

- 用户说“我正在学 FastAPI”时，保存 `profile / current_topic = FastAPI`。
- 用户说“我正在学 RAG”时，保存 `profile / current_topic = RAG`。

验收方式：

- 用 `/memory/extract` 预览候选记忆。
- 用 `/agent/chat` 写入数据库。
- 用 `/users/{user_id}/memories` 查看结果。

这个练习的价值不是写正则，而是判断“当前学习主题”是否值得作为后续回答的上下文。

### 练习二：防止低价值信息写入记忆

尝试输入：

```json
{
  "user_id": "u_001",
  "message": "今天我喝了一杯水。"
}
```

当前规则不会保存它。请解释为什么它通常不适合成为长期记忆。

再思考：如果用户说“我因为胃病每天必须喝温水”，它是否可能值得保存？应该保存成什么 `memory_type`？

### 练习三：观察重复记忆的更新

先输入：

```json
{
  "user_id": "u_001",
  "message": "以后请用中文回答。"
}
```

再输入：

```json
{
  "user_id": "u_001",
  "message": "以后请用英文回答。"
}
```

观察 `reply_language` 是新增两条，还是更新一条。

这个练习对应真实工程能力：长期记忆不是无限追加日志，很多 key 应该被更新。

## 和下一个模块的关系

本模块只学习记忆基础：提取、保存、检索、复用。

下一模块 `09_memory_governance` 会继续处理：

- 用户查看和删除记忆。
- 记忆过期。
- 记忆更新策略。
- 敏感信息拒绝写入。

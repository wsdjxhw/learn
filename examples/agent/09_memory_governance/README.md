# 记忆治理 Memory Governance

这个模块是 Agent 进阶路线的第十步。

上一模块 `08_memory_basics` 已经完成长期记忆的基础闭环：提取、结构化保存、检索和复用。现在进入真实项目里更关键的问题：记忆不能只会写，还必须可治理。

如果 Agent 把密码、API Key、身份证号存成长期记忆，或者用户删除后仍然继续复用，项目就不是“不够智能”，而是有安全和合规风险。

本模块默认使用 mock 模式，不需要 API Key。配置 `MODEL_MODE=deepseek` 后，也可以用 `openai` Python 包的 OpenAI 兼容协议调用 DeepSeek。

## 学习目标

- 理解为什么长期记忆必须有治理能力。
- 学会查看用户当前 active memory。
- 学会软删除记忆，并理解它和物理删除的区别。
- 学会给记忆设置 `expires_at`，并让过期记忆不再参与检索。
- 学会手动更新错误记忆。
- 学会在写入前拒绝敏感信息。
- 学会用审计日志记录记忆创建、更新、删除、过期和使用。

## 文件结构

```text
examples/agent/09_memory_governance
├── main.py
├── settings.py
├── database.py
├── models.py
├── schemas.py
├── memory_extractor.py
├── memory_safety.py
├── memory_store.py
├── context_builder.py
├── provider.py
├── MEMORY_GOVERNANCE_BASICS.md
├── MEMORY_GOVERNANCE_EXPLAINED.md
├── START_HERE.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `settings.py`：读取 `.env` 配置，决定 mock / DeepSeek / 数据库地址。
- `database.py`：SQLAlchemy 引擎、Session 和依赖注入。
- `models.py`：ORM Model，定义聊天历史、长期记忆和审计日志。
- `schemas.py`：请求 DTO 和响应 DTO。
- `memory_extractor.py`：从用户输入里提取候选记忆。
- `memory_safety.py`：敏感信息检测和拒绝写入。
- `memory_store.py`：记忆保存、更新、删除、过期扫描、检索。
- `context_builder.py`：把可使用记忆转换成模型上下文。
- `provider.py`：模型调用层，默认 mock，也支持 DeepSeek。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\09_memory_governance
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

- `module` 是否是 `09_memory_governance`。
- `model_mode` 默认是否是 `mock`。
- `database_url` 是否指向 `sqlite:///./agent_memory_governance.db`。

### 2. 预览普通记忆提取

测试：

```text
POST /memory/extract
```

请求体：

```json
{
  "text": "我是 AI 应用初学者，以后请用中文回答，我正在学习 Agent，我喜欢就业级、企业级讲解。"
}
```

你应该看到：

- `accepted`：可以保存的候选记忆。
- `rejected`：被拒绝的候选记忆，这里通常为空。

重点观察 `retention_days`：

- `reply_language` 没有过期时间。
- `current_topic = Agent` 默认 90 天过期。
- 学习目标、学习阶段默认 365 天过期。

### 3. 预览敏感信息拒绝

测试：

```text
POST /memory/extract
```

请求体：

```json
{
  "text": "我叫小王，我的密码是 abc123，以后请用中文回答。"
}
```

重点看 `rejected`。

这句话里虽然包含“我叫小王”和“以后请用中文回答”，但原文同时包含密码。教学版策略会拒绝由这段原文产生的候选记忆，避免敏感信息进入长期记忆。

### 4. 聊天并写入可治理记忆

测试：

```text
POST /agent/chat
```

请求体：

```json
{
  "user_id": "u_001",
  "message": "我是 AI 应用初学者，以后请用中文回答，我正在学习 Agent，我喜欢就业级、企业级讲解。"
}
```

重点看：

- `extracted_memories`：通过治理的候选记忆。
- `rejected_memories`：被拒绝的候选记忆。
- `saved_memory_count`：真正写入或更新的数量。
- `used_memories`：本轮回答实际使用的 active 且未过期记忆。

### 5. 查看用户记忆

测试：

```text
GET /users/u_001/memories
```

默认不会返回：

- `deleted` 记忆。
- 已经过期的记忆。

如果要调试治理效果，可以加查询参数：

```text
GET /users/u_001/memories?include_deleted=true&include_expired=true
```

### 6. 手动更新一条记忆

先从上一步响应里复制一条 `memory_id`，例如 `reply_language` 对应的 id。

测试：

```text
PATCH /users/u_001/memories/{memory_id}
```

请求体：

```json
{
  "value": "英文",
  "confidence": 0.95,
  "clear_expiration": true,
  "reason": "用户明确要求后续改用英文回答。"
}
```

这个接口演示真实产品里的“用户修正记忆”。

### 7. 删除一条记忆

测试：

```text
DELETE /users/u_001/memories/{memory_id}
```

请求体：

```json
{
  "reason": "用户不希望继续保留这条偏好。"
}
```

删除后再测试：

```text
POST /memory/search
```

请求体：

```json
{
  "user_id": "u_001",
  "query": "帮我规划下一步 Agent 学习内容。",
  "limit": 5
}
```

被删除的记忆不应该再出现在检索结果里。

### 8. 观察过期过滤

找一条记忆，用 PATCH 设置 1 天后过期：

```json
{
  "expires_in_days": 1,
  "reason": "演示记忆过期时间。"
}
```

本模块的接口参数不允许设置过去时间，这是为了避免初学者误操作。真实项目里过期通常由后台任务根据系统时间扫描。

你可以阅读 `memory_store.py` 的 `expire_due_memories()`，理解定时任务如何把到期记忆标记为 `expired`。

接口：

```text
POST /memory/expire-scan
```

这个接口模拟定时任务扫描。当前没有到期记忆时，返回 `expired_count = 0` 是正常的。

## 练习任务

### 练习一：新增一种敏感信息规则

在 `memory_safety.py` 里新增邮箱检测规则。

要求：

- 邮箱格式命中后拒绝写入长期记忆。
- `/memory/extract` 能看到 `risk_type = email`。
- 不要影响普通“以后请用中文回答”的输入。

这个练习对应真实工程能力：安全规则要尽量准确，不能把所有文本都误杀。

### 练习二：给 `current_topic` 做更短的过期策略

现在 `current_topic` 默认 90 天过期。

请把它改成 30 天，并解释为什么“当前学习主题”通常不应该永久保存。

验收方式：

- 用 `/agent/chat` 输入“我正在学习 RAG”。
- 用 `/users/{user_id}/memories` 查看 `expires_at` 是否存在。

### 练习三：删除后重新表达偏好

流程：

1. 输入“以后请用中文回答”。
2. 删除 `reply_language` 记忆。
3. 再输入“以后请用英文回答”。

观察：

- 删除后的旧记忆是否会被检索。
- 重新表达后是否会重新激活同一个 key。
- `value` 是否更新为英文。

这个练习对应真实产品里的一个问题：用户删除不代表永远禁止再次保存，除非产品设计了“永久拒绝此类记忆”的额外规则。

## 和下一个模块的关系

本模块解决“记忆能不能保存、能不能使用、用户能不能修正和删除”。

下一个模块 `10_tool_permissions` 会进入工具工程：Agent 调工具时，哪些工具可以用、哪些工具不能用、读工具和写工具有什么权限边界。

# 短期状态管理 Short Term State

这个模块是 Agent 进阶路线的第八步。

你已经学完上下文工程，知道每次模型调用前要构造 system prompt、当前问题、历史消息、RAG source 和工具 observation。现在进入另一个核心问题：Agent 执行过程中发生了什么，应该保存在哪里？

短期状态管理不是“把聊天记录存起来”。它保存的是一次 Agent run 的执行现场：当前状态、已经执行过哪些 steps、每一步输入输出是什么、失败发生在哪一步、刷新页面后还能不能继续查看。

本模块默认使用 mock 模式，不需要 API Key。配置 `MODEL_MODE=deepseek` 后，也可以用 `openai` Python 包的 OpenAI 兼容协议调用 DeepSeek。

## 学习目标

- 区分一次请求状态、一次 Agent run 状态、聊天历史和长期记忆。
- 理解为什么 Agent 不能只靠函数局部变量保存中间步骤。
- 学会用 SQLite + SQLAlchemy 保存 `agent_runs` 和 `agent_steps`。
- 学会创建 `run_id`，并用它查询当前执行状态。
- 学会保存每一步的输入、输出、耗时位置和错误原因。
- 学会在失败后查看已执行步骤，并从失败 run 恢复执行。
- 理解短期状态如何服务后续的 trace、评测、前端工作台和生产排障。

## 文件结构

```text
examples/agent/07_short_term_state
├── main.py
├── settings.py
├── database.py
├── models.py
├── schemas.py
├── state_store.py
├── tools.py
├── provider.py
├── agent_runner.py
├── SHORT_TERM_STATE_BASICS.md
├── SHORT_TERM_STATE_EXPLAINED.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `settings.py`：读取 `.env` 配置，决定 mock / DeepSeek / 数据库地址。
- `database.py`：SQLAlchemy 引擎、Session 和依赖注入。
- `models.py`：ORM Model，定义 `agent_runs` 和 `agent_steps` 两张表。
- `schemas.py`：请求 DTO 和响应 DTO。
- `state_store.py`：短期状态读写层，封装创建 run、写 step、查询 run。
- `tools.py`：教学版工具，模拟规则检索和退款计算。
- `provider.py`：模型调用层，默认 mock，也支持 DeepSeek。
- `agent_runner.py`：后台执行 Agent steps，并把每一步写入数据库。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\07_short_term_state
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

- `module` 是否是 `07_short_term_state`。
- `model_mode` 默认是否是 `mock`。
- `database_url` 是否指向 `sqlite:///./agent_state.db`。

### 2. 创建一个 Agent run

测试：

```text
POST /agent/runs
```

请求体：

```json
{
  "user_goal": "商品签收 5 天后发现破损，订单 240 元，可以退款吗？",
  "delay_seconds": 1
}
```

你会拿到：

```json
{
  "run_id": "一串 UUID",
  "status": "pending",
  "query_url": "/agent/runs/一串 UUID"
}
```

这里的重点是：接口不会要求你等 Agent 全部执行完才返回。它先返回 `run_id`，后续通过查询接口看状态。

### 3. 查询执行中的状态

立刻测试：

```text
GET /agent/runs/{run_id}
```

如果你把 `delay_seconds` 调大，可能会看到：

- `pending`：run 已创建，还没开始执行。
- `running`：正在执行。
- `succeeded`：已经完成。
- `failed`：执行失败。

同时观察 `steps`：

- `plan`：拆解用户目标。
- `tool_call/search_refund_policy`：检索售后规则。
- `tool_call/calculate_refund_amount`：计算退款金额。
- `final_answer/generate_final_answer`：生成最终回答。

### 4. 刷新后找回 run

测试：

```text
GET /agent/runs
```

这个接口会列出最近 run。它证明短期状态已经进入数据库，不依赖当前页面或 Python 函数变量。

### 5. 制造一次失败

测试：

```text
POST /agent/runs
```

请求体：

```json
{
  "user_goal": "商品签收 5 天后发现破损，订单 240 元，可以退款吗？",
  "simulate_failure_at_step": 2,
  "delay_seconds": 1
}
```

等待一会儿后查询：

```text
GET /agent/runs/{run_id}
```

你应该看到：

- run 状态变成 `failed`。
- 第 1 步 `plan` 已经保存。
- 错误 step 记录了失败原因。
- `error` 字段能告诉你失败发生在哪里。

这就是短期状态的核心价值：失败不是一片空白，而是留下可排查现场。

### 6. 恢复失败 run

测试：

```text
POST /agent/runs/{run_id}/resume
```

请求体：

```json
{
  "clear_failure": true,
  "delay_seconds": 1
}
```

再查询：

```text
GET /agent/runs/{run_id}
```

你会看到 Agent 基于已有状态继续执行，最终进入 `succeeded`。

## 真实模型模式

`.env` 可以改成：

```text
MODEL_MODE=deepseek
DEEPSEEK_API_KEY=你的真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

然后重启服务。

真实模型只用于最后一步 `generate_final_answer`。前面的状态保存、工具执行、失败恢复逻辑都不依赖真实模型。

## 练习任务

### 练习 1：增加 step 耗时字段

现在 step 保存了 `started_at` 和 `finished_at`。请你在响应里增加：

```text
duration_ms
```

要求：

- 根据开始和结束时间计算毫秒数。
- 如果 `finished_at` 为空，返回 `null`。
- 在 `/agent/runs/{run_id}` 能看到每一步耗时。

学习价值：生产 Agent 排障时，必须知道慢在模型、检索、数据库还是工具。

### 练习 2：增加取消 run 接口

新增：

```text
POST /agent/runs/{run_id}/cancel
```

要求：

- 只有 `pending` 或 `running` 可以取消。
- 取消后状态变成 `failed` 或新增 `cancelled`。
- 写入一条 step，说明是谁取消、什么时候取消。

学习价值：真实产品里用户可能关闭页面、撤销任务，Agent 不能无限执行。

### 练习 3：保存 tool error 的结构化信息

现在错误主要存在 `error` 字符串里。请你改成：

```json
{
  "error_code": "TOOL_TIMEOUT",
  "message": "工具超时",
  "retryable": true
}
```

要求：

- `output_json` 保存结构化错误。
- `/resume` 只能恢复 `retryable=true` 的失败。

学习价值：工程里不能只靠自然语言错误文案判断是否能重试。

### 练习 4：把 run 和聊天会话关联起来

给 `AgentRun` 增加：

```text
session_id
```

要求：

- 创建 run 时可以传 `session_id`。
- 查询列表时支持按 `session_id` 过滤。
- 文档里解释 `session_id` 和 `run_id` 的区别。

学习价值：聊天历史解决“用户说过什么”，run 状态解决“Agent 正在做什么”，两者经常需要关联但不能混为一谈。

## 本模块暂时不做什么

- 不做多用户权限。
- 不做 Redis 队列。
- 不做真正分布式 worker。
- 不做完整 trace 平台。
- 不做长期记忆。

这些会在后面的记忆工程、工具权限、后台任务智能体、可观测性和生产部署模块继续展开。

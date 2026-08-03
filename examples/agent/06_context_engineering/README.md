# 上下文工程 Context Engineering

这个模块是 Agent 进阶路线的第七步。

你已经学完结构化输出，知道模型输出必须被后端解析、校验和降级。本模块继续学习模型调用的另一半：模型每次回答前，到底应该看到哪些内容。

上下文工程要管理的不只是用户问题，还包括 system prompt、历史消息、RAG 资料、工具 observation，以及上下文长度预算。生产 Agent 的很多错误不是模型“不会”，而是后端给模型看的上下文太少、太旧、太乱或太长。

本模块默认使用 mock 模式，不需要 API Key。配置 `MODEL_MODE=deepseek` 后，也可以用 OpenAI 兼容协议调用 DeepSeek。

## 学习目标

- 理解上下文不是聊天记录的简单拼接。
- 理解 system prompt、当前问题、历史消息、RAG sources、工具 observation 的职责差异。
- 学会写一个教学版 `build_context()`。
- 学会按优先级和 token 预算裁剪历史消息。
- 学会过滤低相关 RAG，避免无关资料干扰回答。
- 学会把工具 observation 注入上下文，让模型基于执行结果继续回答。
- 学会用 `/context/preview` 调试模型真正看到的输入。

## 文件结构

```text
examples/agent/06_context_engineering
├── main.py
├── settings.py
├── schemas.py
├── sample_data.py
├── context_builder.py
├── provider.py
├── agent.py
├── CONTEXT_ENGINEERING_BASICS.md
├── CONTEXT_ENGINEERING_EXPLAINED.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `settings.py`：读取 `.env` 配置，决定用 mock 还是真实模型。
- `schemas.py`：请求 DTO 和上下文结果结构。
- `sample_data.py`：提供教学场景数据，避免一开始就引入数据库。
- `context_builder.py`：本模块核心，负责构造、排序、过滤、裁剪上下文。
- `provider.py`：模型调用层，默认 mock，也支持 DeepSeek。
- `agent.py`：串起上下文构造和模型调用。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\06_context_engineering
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

先测试：

```text
GET /health
```

重点看：

- `module` 是否是 `06_context_engineering`。
- `model_mode` 默认是否是 `mock`。
- `has_deepseek_api_key` 是否符合你的 `.env` 配置。

### 2. 查看教学场景

测试：

```text
GET /demo-cases
```

你会看到：

- `clean`：干净上下文。
- `long_history`：历史消息很多。
- `noisy_rag`：混入低相关 RAG。
- `tool_result`：工具成功 observation。
- `tool_error`：工具失败 observation。

### 3. 预览干净上下文

测试：

```text
POST /context/preview
```

请求体：

```json
{
  "message": "商品签收 5 天后发现破损，订单 240 元，可以退款吗？",
  "context_scenario": "clean",
  "max_context_tokens": 700
}
```

重点观察：

- `messages` 才是准备发给模型的内容。
- `source_type` 标记上下文来源。
- `keep_reason` 解释为什么保留。
- `omitted_items` 解释哪些内容被丢弃。

### 4. 观察历史裁剪

把请求体改成：

```json
{
  "message": "商品签收 5 天后发现破损，订单 240 元，可以退款吗？",
  "context_scenario": "long_history",
  "max_context_tokens": 220,
  "max_history_messages": 8
}
```

你应该看到部分历史进入 `omitted_items`。这说明历史消息不能无限塞，必须按预算和价值裁剪。

### 5. 运行 Agent

测试：

```text
POST /agent/run
```

请求体：

```json
{
  "message": "商品签收 5 天后发现破损，订单 240 元，可以退款吗？",
  "context_scenario": "clean",
  "max_context_tokens": 700
}
```

mock 模式下应该能看到回答引用 `refund-policy-001`。

### 6. 对比低相关 RAG 干扰

测试：

```text
POST /agent/compare-noisy-context
```

请求体：

```json
{
  "message": "商品签收 5 天后发现破损，订单 240 元，可以退款吗？",
  "max_context_tokens": 900
}
```

重点对比：

- `strict.context.omitted_items`：低相关会员和营销资料被过滤。
- `strict.answer`：仍然围绕退款回答。
- `loose.answer`：被低相关会员资料干扰。

这就是本模块最重要的工程结论：上下文不是越多越好。

### 7. 注入工具成功结果

请求体：

```json
{
  "message": "请根据刚才工具结果告诉客户退款金额。",
  "context_scenario": "tool_result",
  "max_context_tokens": 700
}
```

你应该看到上下文里出现 `[工具观察]`，回答会优先使用 `refund_amount`。

### 8. 注入工具失败结果

请求体：

```json
{
  "message": "如果退款工具失败，下一步应该怎么办？",
  "context_scenario": "tool_error",
  "max_context_tokens": 700
}
```

你应该看到模型基于工具失败原因说明缺少签收时间，而不是假装已经算出退款。

## 真实模型模式

`.env` 可以改成：

```text
MODEL_MODE=deepseek
DEEPSEEK_API_KEY=你的真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

然后重启服务。

真实模型模式仍然会先经过 `build_context()`。不要把所有原始 history、sources、observations 直接丢给模型。

## 练习任务

### 练习 1：调整历史消息保留策略

当前代码只保留最近历史。请你改成：

- 最近 4 条消息优先保留。
- 如果历史里包含“订单金额”“购买天数”“破损”，即使更早也可以保留。

学习价值：真实 Agent 不只看“新旧”，还要看历史是否包含关键槽位信息。

### 练习 2：给 RAG source 增加 `reason`

在 `RagSource` 里新增字段：

```text
reason
```

要求 `context_builder.py` 把 reason 一起放进上下文，说明为什么这条资料被检索出来。

学习价值：让模型不仅看到资料，还看到检索系统为什么认为它相关。

### 练习 3：设计 observation 优先级

现在所有工具 observation 都按最近 3 条保留。请你改成：

- 成功的写操作 observation 优先级最高。
- 失败 observation 也要保留错误原因。
- 超过预算时，普通查询 observation 可以被丢弃。

学习价值：训练你区分工具结果的业务风险和上下文价值。

### 练习 4：让 `/context/preview` 返回前端友好的统计

新增一个字段：

```text
context_stats
```

包含：

- history_count_kept
- rag_count_kept
- tool_observation_count_kept
- omitted_count

学习价值：前端工作台和可观测性模块都会需要这类统计。

## 本模块暂时不做什么

- 不做精确 tokenizer。
- 不做数据库保存。
- 不做长期记忆。
- 不做复杂 prompt injection 防护。
- 不做 Agent trace 持久化。

这些会在后面的短期状态、记忆工程、安全、可观测性和成本模块继续学习。

# 上下文工程代码讲解

这份文档按代码执行顺序解释本模块。建议先运行 `/context/preview`，再对照这里看代码。

## 1. `main.py`：接口层

`main.py` 创建 FastAPI 应用：

```python
app = FastAPI(title="Context Engineering Teaching Demo")
```

Java 类比：`main.py` 类似 Controller，负责接收 HTTP 请求和返回 HTTP 响应。

它提供四类接口：

- `GET /health`：确认服务和模型模式。
- `GET /demo-cases`：查看教学场景。
- `POST /context/preview`：只构造上下文，不调用模型。
- `POST /agent/run`：构造上下文后调用模型。
- `POST /agent/compare-noisy-context`：对比严格过滤和宽松注入的差异。

本模块特意把 `/context/preview` 单独做出来，因为上下文工程必须可调试。真实项目里如果看不到模型输入，就很难排查 Agent 为什么答错。

## 2. `schemas.py`：请求 DTO 和结果结构

`ContextBuildRequest` 是最重要的请求模型。

它包含：

- `message`：当前用户问题。
- `history`：历史消息。
- `rag_sources`：RAG 检索资料。
- `tool_observations`：工具执行结果。
- `max_context_tokens`：上下文预算。
- `rag_min_relevance`：RAG 最低相关性阈值。

`history`、`rag_sources`、`tool_observations` 都是可选字段。不传时，`sample_data.py` 会根据 `context_scenario` 提供教学数据。

`ContextMessage` 表示最终准备发给模型的一条消息。它比真实模型 API 多了几个教学字段：

- `source_type`：这条消息来自哪里。
- `approx_tokens`：近似 token 数。
- `keep_reason`：为什么保留。

这些字段不会发给真实模型，但会返回给前端或学习者观察。

## 3. `sample_data.py`：教学数据

`sample_data.py` 提供五个场景：

- `clean`：少量历史和高相关 RAG。
- `long_history`：历史很多，用来观察裁剪。
- `noisy_rag`：混入会员和营销资料，用来观察干扰。
- `tool_result`：工具成功返回退款金额。
- `tool_error`：工具失败返回错误原因。

真实项目里这些数据通常来自数据库、RAG 服务和工具执行日志。本模块先用内存数据，是为了让初学者先理解上下文本身。

## 4. `context_builder.py`：核心上下文构造

`build_context()` 是本模块核心函数。

它的执行流程是：

```text
读取输入或教学数据
-> 放入 system prompt
-> 预留当前用户问题
-> 按优先级选择工具 observation
-> 过滤并选择 RAG source
-> 从最近历史里选择可放入的消息
-> 追加当前用户问题
-> 返回 messages 和 omitted_items
```

### 为什么当前问题最后追加

聊天模型通常会更关注靠近末尾的用户问题。本模块把当前问题放在最后，是为了让模型明确知道这次要回答什么。

### 为什么 observation 优先于历史

工具 observation 是 Agent 刚刚执行工具得到的新事实。

如果工具已经算出 `refund_amount=240`，模型应该优先使用这个结果，而不是重新从历史里猜。

### 为什么 RAG 要过滤

`rag_min_relevance` 默认是 `0.55`。低于阈值的资料会进入 `omitted_items`。

这一步非常关键。RAG 资料只要进入上下文，就可能影响模型注意力。无关资料不是中性的，它会增加误答概率。

### 为什么要记录 omitted_items

被丢弃的上下文也要有记录。真实排查时，常见问题是：

- 用户明明说过订单金额，为什么模型不知道？
- 某条 RAG source 明明被检索到了，为什么回答没引用？
- 工具已经执行了，为什么模型还说缺少结果？

`omitted_items` 可以回答这些问题。

## 5. `provider.py`：模型调用层

`provider.py` 支持两种模式：

- `mock`：默认模式，不需要 API Key。
- `deepseek`：通过 OpenAI 兼容协议调用 DeepSeek。

mock 模式会根据上下文关键词稳定返回结果：

- 看到 `refund_amount`：说明工具结果已注入。
- 看到 `工具执行失败`：说明工具错误已注入。
- 看到退款政策：按 RAG source 回答。
- 看到黑金会员资料：故意展示低相关资料造成的干扰。

这不是为了模拟真实智能，而是为了稳定展示上下文变化造成的行为变化。

## 6. `agent.py`：串联流程

`run_context_agent()` 做三件事：

```text
校验请求
-> build_context()
-> generate_model_answer()
```

它不直接处理 HTTP，也不直接读取 `.env`。这样以后写测试时，可以直接调用 `run_context_agent()`，不用启动 Web 服务。

## 7. 推荐阅读顺序

先看：

```text
README.md
```

再看：

```text
CONTEXT_ENGINEERING_BASICS.md
```

然后按顺序读代码：

```text
schemas.py
sample_data.py
context_builder.py
provider.py
agent.py
main.py
```

最后回到 `/docs` 里跑：

```text
/context/preview
/agent/run
/agent/compare-noisy-context
```

如果你能解释 `messages` 里每一条为什么被保留、`omitted_items` 里每一条为什么被丢弃，就说明本模块核心已经掌握。

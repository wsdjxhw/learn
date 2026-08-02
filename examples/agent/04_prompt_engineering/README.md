# 提示词工程 Prompt Engineering

这个模块是 Agent 进阶路线的第五步。

你已经学过多工具编排后，本模块开始学习：不要把 prompt 当成随手写在代码里的字符串，而要把它当成可以版本化、可以对比、可以回滚的工程资产。

本模块不调用真实外部模型，而是使用教学版 `mock_model.py` 读取 prompt 文件里的策略标记，稳定模拟不同 prompt 对工具选择的影响。这样你可以先学清楚 prompt 工程的后端结构，再去接真实模型。

## 学习目标

- 理解 system prompt 在 Agent 中的职责。
- 理解 prompt 为什么不应该写死在代码里。
- 理解 prompt 版本管理。
- 理解 `.env` 中的 `PROMPT_VERSION` 如何控制默认版本。
- 对比不同 prompt 对工具选择的影响。
- 理解 prompt 改动为什么可能破坏工具调用。
- 学会保留旧 prompt，并用同一组输入比较新旧版本效果。

## 文件结构

```text
examples/agent/04_prompt_engineering
├── main.py
├── settings.py
├── prompt_store.py
├── mock_model.py
├── agent.py
├── tools.py
├── prompts
│   ├── v1_direct_answer.md
│   └── v2_tool_first.md
├── PROMPT_ENGINEERING_BASICS.md
├── PROMPT_ENGINEERING_EXPLAINED.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `settings.py`：读取 `.env` 配置。
- `prompt_store.py`：读取 prompt 文件，列出 prompt 版本。
- `mock_model.py`：教学版模型，用稳定规则模拟 prompt 对行为的影响。
- `agent.py`：把 prompt、模型决策和工具调用串起来。
- `tools.py`：工具白名单和工具执行逻辑。
- `prompts/`：不同版本的 prompt 文件。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\04_prompt_engineering
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

- `default_prompt_version`：默认 prompt 版本，来自 `.env`。
- `available_prompt_versions`：当前有哪些 prompt 文件。
- `tool_count`：当前工具数量。

### 2. 查看 prompt 版本

测试：

```text
GET /prompts
```

你会看到：

- `v1_direct_answer`
- `v2_tool_first`

重点看 `behavior`：

- `DIRECT_ANSWER`：倾向直接回答。
- `TOOL_FIRST`：涉及退款金额时先用工具。

### 3. 查看某个 prompt 内容

测试：

```text
GET /prompts/v2_tool_first
```

重点观察：

- 角色是什么。
- 什么情况下必须调用工具。
- 工具顺序是否写清楚。
- 禁止事项是否写清楚。

### 4. 用 v1 运行 Agent

测试：

```text
POST /agent/run
```

请求体：

```json
{
  "message": "客户说商品破损，订单 240 元，购买 5 天，帮我判断退款金额。",
  "prompt_version": "v1_direct_answer",
  "order_amount": 240,
  "days_since_purchase": 5,
  "item_problem": "破损"
}
```

你应该看到：

- `tool_call_count` 是 `0`。
- 回答比较模糊。
- `steps` 里只有 `model_decision`。

这说明 v1 prompt 没有把“退款金额必须由工具计算”写清楚。

### 5. 用 v2 运行 Agent

把 `prompt_version` 改成：

```json
"v2_tool_first"
```

你应该看到：

- 先调用 `search_refund_policy`。
- 再调用 `calculate_refund`。
- `tool_call_count` 是 `2`。
- 最终回答包含计算出的退款金额。

### 6. 对比两个 prompt 版本

测试：

```text
POST /agent/compare
```

请求体：

```json
{
  "message": "客户说商品破损，订单 240 元，购买 5 天，帮我判断退款金额。",
  "versions": ["v1_direct_answer", "v2_tool_first"],
  "order_amount": 240,
  "days_since_purchase": 5,
  "item_problem": "破损"
}
```

重点比较：

- 两个版本的 `tool_call_count`。
- 两个版本的 `steps`。
- 哪个版本更适合退款金额这种需要准确计算的场景。

## 练习任务

### 练习 1：新增一个 prompt 版本

复制 `prompts/v2_tool_first.md`，创建：

```text
prompts/v3_strict_refund.md
```

要求它更严格：

- 如果超过 7 天且不是质量问题，只能建议人工审核。
- 不允许承诺具体到账时间。
- 工具失败时必须说明不能自动判断。

然后把 `.env` 改成：

```text
PROMPT_VERSION=v3_strict_refund
```

学习价值：练习 prompt 版本新增、默认版本切换和回滚。

### 练习 2：观察 prompt 改动如何破坏工具调用

把 `v2_tool_first.md` 里的：

```text
PROMPT_BEHAVIOR: TOOL_FIRST
```

改成：

```text
PROMPT_BEHAVIOR: UNKNOWN
```

再请求 `/agent/run`。

你会看到 mock model 进入保守停止路径。

学习价值：真实项目里 prompt 格式、约定、工具名变动都可能破坏工具调用，所以 prompt 也需要测试。

### 练习 3：设计一组固定对比样例

手动准备三组输入：

- 破损、5 天、240 元。
- 不喜欢、5 天、240 元。
- 不喜欢、10 天、240 元。

分别用 `/agent/compare` 对比 v1 和 v2。

学习价值：不要只靠一个样例判断 prompt 好坏。prompt 改动要用多种输入验证。

## 本模块暂时不做什么

- 不调用真实 DeepSeek。
- 不做 JSON Schema 严格输出校验。
- 不做自动评分。
- 不把 prompt 存进数据库。

这些会在后面的结构化输出、上下文工程、Agent 评测和运行基座模块继续学习。

# 最小 Agent 循环 Minimal Agent Loop

这个模块是 Agent 进阶路线的第三步。

你已经学过“工具调用”后，本模块开始学习 Agent 的核心循环：

```text
用户目标
-> 模型决策
-> 工具调用
-> observation
-> 下一轮模型决策
-> 最终回答
```

本模块支持真实 DeepSeek 工具调用；如果没有 `DEEPSEEK_API_KEY`，会自动退回 mock 模式，保证无 key 也能运行。学习重点是循环、真实模型决策、停止条件、失败处理和 steps 记录。

## 学习目标

- 理解 Agent Loop 为什么是 Agent 的核心。
- 理解 `model decision -> tool call -> observation -> final answer`。
- 理解 `max_steps` 为什么必须存在。
- 理解工具成功、工具失败、继续执行和停止执行。
- 理解真实模型如何根据 observation 决定下一步。
- 理解为什么仍然需要 mock 模式做稳定教学和本地调试。
- 能通过 `steps` 看懂 Agent 每一轮做了什么。

## 文件结构

```text
examples/agent/02_minimal_agent_loop
├── main.py
├── agent_loop.py
├── provider.py
├── tools.py
├── AGENT_LOOP_BASICS.md
├── AGENT_LOOP_EXPLAINED.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `agent_loop.py`：Agent 循环编排层，负责控制每一轮执行。
- `provider.py`：模型决策层，有 key 调 DeepSeek，无 key 自动 mock。
- `tools.py`：工具定义、参数校验和工具执行入口。
- `AGENT_LOOP_BASICS.md`：基础概念扫盲。
- `AGENT_LOOP_EXPLAINED.md`：逐段解释代码结构。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\02_minimal_agent_loop
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置模板：

```powershell
Copy-Item .env.example .env
```

如果要使用真实 DeepSeek，把 `.env` 里的 `DEEPSEEK_API_KEY` 改成真实 key。

如果不填 key，模块会自动进入 mock 模式，仍然可以跑通完整 Agent Loop。

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

- `provider` 当前是 `deepseek` 还是 `mock`。
- `has_api_key` 表示是否读到了真实 key。
- `model` 表示真实模型名；mock 模式下仍会显示默认模型配置。
- `default_max_steps` 默认最大执行轮数。
- `tool_count` 当前工具数量。

### 2. 查看工具清单

再测试：

```text
GET /tools
```

先知道 Agent 能调用哪些工具，再看 `/agent/run` 的 steps 会更容易理解。

### 3. 测试一步工具调用

测试：

```text
POST /agent/run
```

请求体：

```json
{
  "message": "帮我查深圳天气，然后给一个出门建议",
  "max_steps": 3,
  "allow_tools": true,
  "system_prompt": "你是一个教学版 Agent。需要工具时调用工具，信息足够时直接最终回答。"
}
```

你应该看到：

```text
model_decision -> observation -> model_decision -> final_answer
```

重点观察：

- 第一轮 decision 选择 `get_weather`。
- 第一轮 observation 保存天气工具结果。
- 第二轮 decision 发现信息足够，返回最终回答。

### 4. 测试多轮工具调用

请求体：

```json
{
  "message": "帮我查深圳天气，再看报销制度，最后给一个出差提醒",
  "max_steps": 4,
  "allow_tools": true
}
```

你应该看到 Agent 先查天气，再查报销制度，最后汇总回答。

### 5. 测试工具失败

请求体：

```json
{
  "message": "帮我查火星天气",
  "max_steps": 3,
  "allow_tools": true
}
```

`火星` 不在天气假数据里，工具会失败。Agent 不会让接口崩溃，而是在下一轮解释失败原因并停止。

### 6. 测试最大步数保护

请求体：

```json
{
  "message": "循环测试：请一直检查报销制度",
  "max_steps": 2,
  "allow_tools": true
}
```

这个输入会故意让 mock 决策持续调用工具。你应该看到：

```json
"stopped_by": "max_steps"
```

这说明后端主动截停，避免 Agent 无限循环。

## 练习任务

### 练习 1：增加一个失败后的降级回答

当前工具失败后，Agent 会直接停止并解释失败原因。

请修改 `provider.py` 里的 mock 失败处理：

- 当 `get_weather` 失败时，不只是说失败。
- 再补一句“可以换一个支持的城市，例如北京、上海、深圳、广州、新加坡”。

学习价值：练习把工具失败转换成用户能理解的下一步建议。

### 练习 2：新增一个需要两步完成的用户目标

请设计一个新问题，例如：

```text
帮我计算订单总价，再查退款制度
```

要求：

- 第一轮调用 `calculate_order_total`。
- 第二轮调用 `search_policy`。
- 最终回答同时包含订单金额和退款制度。

学习价值：练习读懂完整链路，而不是只复制一个接口。

### 练习 3：给 steps 增加耗时字段

请在 `agent_loop.py` 里记录每一轮工具调用耗时。

要求：

- 只记录工具执行耗时即可。
- 返回字段可以叫 `duration_ms`。
- 通过 `/docs` 调用后能看到每次工具用了多久。

学习价值：这是后续 trace、日志和可观测性的前置能力。

### 练习 4：观察真实模型和 mock 的差异

请分别在有 key 和无 key 两种模式下测试同一个问题：

```text
帮我查深圳天气，再看报销制度，最后给一个出差提醒
```

要求：

- 对比 `provider` 字段。
- 对比每一轮 `model_decision` 里的 `thought`、`tool_name` 和 `arguments`。
- 观察真实模型是否可能和 mock 选择不同的调用顺序。

学习价值：理解真实模型决策不是固定规则，所以后端必须保留 `max_steps`、工具白名单和参数校验。

## 推荐阅读顺序

1. 先读 `AGENT_LOOP_BASICS.md`。
2. 跑通 `/agent/run`。
3. 再读 `AGENT_LOOP_EXPLAINED.md`。
4. 最后改练习任务。

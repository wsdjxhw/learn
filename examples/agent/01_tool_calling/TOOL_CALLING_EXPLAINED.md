# Tool Calling 代码讲解

这个模块有三个核心文件：

- `tools.py`：定义工具和工具白名单。
- `provider.py`：决定是否调用工具。
- `main.py`：提供 HTTP 接口，把完整流程串起来。

## `tools.py`

`TOOL_SCHEMAS` 是工具说明书。

它不是给 Python 执行用的，而是给模型理解工具用的。每个 schema 都说明：

- 工具叫什么。
- 工具适合解决什么问题。
- 调用工具时需要哪些参数。

本模块提供三个工具：

- `get_weather`：查询教学版天气。
- `calculate_order_total`：计算订单金额。
- `search_policy`：检索教学版制度资料。

这些工具都不调用真实外部服务，目的是先让你看懂工具调用流程。

## `run_tool()`

`run_tool()` 是工具执行入口。

它接收两个参数：

```python
tool_name: str
arguments: dict[str, Any]
```

`tool_name` 表示要调用哪个工具。

`arguments` 表示工具参数。它来自 `/tool/run` 的请求体，或者来自模型决策结果。

代码里使用 `if tool_name == ...` 明确分发，而不是让模型随便调用任意 Python 函数。这是工具调用里非常重要的安全边界。

真实项目里也应该使用工具白名单，不应该让模型直接决定运行什么代码。

## 工具错误

`ToolExecutionError` 用来表示工具业务失败。

例如：

- 城市不存在。
- 数量小于等于 0。
- 优惠码不支持。
- 制度资料没有匹配结果。

这些不是程序崩溃，而是可预期的业务失败，所以 `run_tool()` 会把它们转换成：

```json
{
  "ok": false,
  "error": "错误原因"
}
```

这样接口仍然能返回正常 JSON，学习者也能在 `/docs` 里观察失败结果。

## `provider.py`

`provider.py` 负责模型相关逻辑。

它读取 `.env` 中的：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`

如果没有真实 key，就使用 mock 模式。

## mock 决策

`generate_mock_decision()` 用关键词模拟模型判断。

例如：

```text
深圳今天会下雨吗？
```

会被识别成：

```json
{
  "type": "tool_call",
  "tool_name": "get_weather",
  "arguments": {
    "city": "深圳"
  }
}
```

如果用户只是问：

```text
什么是工具调用？
```

就会返回：

```json
{
  "type": "answer"
}
```

这表示不需要工具，直接回答即可。

## 真实 DeepSeek 决策

`generate_deepseek_decision()` 会把 `tools.py` 里的 schema 传给 DeepSeek。

模型可能返回两种结果：

- 普通文本回答。
- `tool_calls`。

如果返回 `tool_calls`，后端会取第一个工具调用，然后由本地 `run_tool()` 执行。

本模块只处理第一个工具调用，因为多工具、多轮调用属于下一节 Agent Loop。

## 最终回答

工具返回的是结构化结果，不一定适合直接给用户看。

`generate_final_answer()` 负责把工具结果整理成最终回答。

mock 模式下，代码直接用固定规则生成中文回答。

真实 DeepSeek 模式下，代码会把工具结果作为 `tool` 消息交回模型，让模型生成自然语言回答。

## `main.py`

`main.py` 是 FastAPI 接口层。

它定义两个请求 DTO：

- `ChatRequest`
- `ToolRunRequest`

`BaseModel` 类似 Java 里的请求 DTO。FastAPI 会自动把 JSON 请求体转换成这些对象。

## `/health`

`GET /health` 用于确认服务状态。

它会返回：

- 服务是否启动。
- 当前 provider。
- 当前模型名。
- 是否有 API Key。
- 当前工具数量。

## `/tools`

`GET /tools` 返回工具 schema。

这个接口能让你直接看到模型能用哪些工具，以及工具参数长什么样。

## `/tool/run`

`POST /tool/run` 用于手动执行工具。

学习时建议先测这个接口，因为它绕过模型，只验证工具本身是否能跑通。

如果工具本身都不稳定，再接模型会更难排查。

## `/chat`

`POST /chat` 是完整工具调用链路。

执行流程是：

```text
1. 记录用户输入。
2. 调用 provider 判断下一步。
3. 如果 provider 选择直接回答，就返回 answer。
4. 如果 provider 选择工具调用，就执行 run_tool。
5. 把工具结果整理成最终回答。
6. 返回 reply 和 steps。
```

`steps` 是为了教学额外返回的中间步骤。

真实产品不一定会把所有中间步骤暴露给用户，但学习阶段应该先看清楚链路。

## `allow_tool`

`allow_tool` 是请求体里的布尔开关。

当它是 `false` 时，后端会禁止工具调用。

这可以帮助你对比：

- 有工具时，系统能查数据、算金额、检索资料。
- 没工具时，系统只能直接回答。

这个开关也对应真实项目里的权限控制：不是所有用户、所有场景都应该允许调用所有工具。

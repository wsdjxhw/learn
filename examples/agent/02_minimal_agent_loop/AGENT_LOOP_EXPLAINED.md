# 最小 Agent 循环代码讲解

这个模块的核心文件是：

```text
main.py -> agent_loop.py -> provider.py -> tools.py
```

## main.py：接口层

`main.py` 类似 Java Controller。

它定义三个接口：

- `GET /health`：确认服务是否启动。
- `GET /tools`：查看当前可用工具。
- `POST /agent/run`：运行一次 Agent Loop。

`AgentRunRequest` 继承 `BaseModel`，可以理解成请求 DTO。

```python
class AgentRunRequest(BaseModel):
    message: str
    max_steps: int | None = None
    allow_tools: bool = True
    system_prompt: str = "..."
```

`message` 来自请求体 JSON，不是查询参数。

`max_steps` 用来限制 Agent 最多执行几轮。它是 `int | None`，意思是可以传整数，也可以不传。不传时读取 `.env` 里的默认值。

`allow_tools` 用来对比两种效果：

- `true`：允许进入工具调用。
- `false`：只直接回答，不执行工具。

`system_prompt` 会传给真实 DeepSeek。

它的作用是告诉模型在 Agent Loop 里应该如何工作：什么时候调用工具，什么时候停止并给最终回答。

## agent_loop.py：循环编排层

`run_agent()` 是本模块最重要的函数。

它负责组织这条链路：

```text
模型决策 -> 工具执行 -> observation -> 下一轮模型决策
```

关键变量有两个：

- `steps`：返回给用户看的完整执行过程。
- `observations`：传给下一轮模型决策看的工具结果。

`for step_number in range(1, max_steps + 1)` 是最大步数保护。

这里故意不用 `while True`，因为初学者很容易写出停不下来的循环。`for` 循环天然会在指定次数后结束。

当 `decision["type"] == "final_answer"` 时，说明 Agent 已经可以停止，函数直接 `return`。

当 `decision["type"] == "tool_call"` 时，说明 Agent 还需要执行工具。后端会调用：

```python
run_tool(
    tool_name=decision["tool_name"],
    arguments=decision["arguments"],
)
```

工具结果会被包装成 observation，加入 `observations`，供下一轮判断使用。

如果循环用完了所有步数还没有最终回答，函数会返回：

```json
{
  "status": "stopped",
  "stopped_by": "max_steps"
}
```

这代表后端主动停止，避免无限循环。

## provider.py：模型决策层

`provider.py` 是本模块最重要的学习点之一。

它同时支持两种模式：

- 有 `DEEPSEEK_API_KEY`：调用真实 DeepSeek，让模型自己决定是否 tool_call。
- 没有 key：使用 mock 规则，保证无 key 也能跑通完整链路。

真实模型决策通常会看：

- system prompt。
- 用户目标。
- 工具 schema。
- observation。

`provider.py` 每一轮会返回两种结构之一：

```json
{"type": "tool_call", "tool_name": "...", "arguments": {...}}
```

或者：

```json
{"type": "final_answer", "answer": "..."}
```

这就是“模型决策契约”。`agent_loop.py` 只认这两种类型。

真实 DeepSeek 模式下，`provider.py` 会把已有 observation 作为 JSON 文本传回模型，让模型判断下一步：

```text
已有 observation -> DeepSeek 判断继续调用工具还是最终回答
```

mock 模式下，`provider.py` 用关键词规则模拟同样的决策过程。

如果上一轮工具失败，mock 模式会选择停止：

```text
上一轮工具失败 -> final_answer -> 解释失败原因
```

这能避免工具失败后继续乱调用。

## tools.py：工具层

`tools.py` 负责三件事：

- 定义工具 schema。
- 实现具体工具函数。
- 提供统一执行入口 `run_tool()`。

`run_tool()` 是工具白名单。

即使模型要求调用某个工具，后端也不会直接执行任意函数。后端只允许调用白名单里的工具：

- `get_weather`
- `calculate_order_total`
- `search_policy`

如果工具名不存在，会返回错误：

```json
{
  "ok": false,
  "error": "工具 xxx 不在白名单中"
}
```

工具失败不会让接口崩溃，而是变成 observation。下一轮 Agent 会看到失败原因，再决定停止或继续。

## 读代码顺序

建议按这个顺序读：

1. 先读 `README.md` 跑通接口。
2. 再读 `main.py`，理解请求从哪里进入。
3. 再读 `agent_loop.py`，理解循环如何执行。
4. 再读 `provider.py`，理解真实模型和 mock 如何共用同一个决策契约。
5. 最后读 `tools.py`，理解工具如何校验参数和返回结果。

# 什么是 Agent 代码讲解

这个模块有三个代码文件：

- `main.py`：HTTP 接口入口。
- `agent.py`：最小 Agent 流程。
- `tools.py`：Agent 可以执行的教学版动作。

## `main.py`

`main.py` 使用 FastAPI 提供接口。

它定义了两个请求 DTO：

- `ChatRequest`
- `AgentRunRequest`

`BaseModel` 类似 Java 里的请求 DTO。FastAPI 会根据请求体 JSON 自动创建这些对象。

## `/chat/basic`

这个接口调用：

```python
basic_chat_reply(message=payload.message)
```

它代表普通聊天流程：

```text
输入 -> 回答
```

它不会执行动作，也不会返回中间步骤。

## `/agent/run`

这个接口调用：

```python
run_minimal_agent(...)
```

它代表最小 Agent 流程：

```text
目标 -> 思考 -> 动作 -> 观察 -> 回答
```

返回值里的 `steps` 是本模块最重要的学习材料。

## `agent.py`

`agent.py` 负责把动作串起来。

它不是模型文件，而是 Agent 的流程控制文件。

## `basic_chat_reply()`

这个函数演示普通聊天。

它只返回一段回答：

```python
{
    "reply": "...",
    "mode": "basic_chat"
}
```

它没有 `steps`，因为普通聊天没有显式的中间动作。

## `decide_action()`

这个函数模拟 Agent 的“思考”。

真实项目里，这一步通常由大模型完成。

当前模块用 `if` 判断，是为了让初学者先看懂逻辑：

- 看到“学习、计划”，选择 `make_learning_plan`。
- 看到“任务、待办”，选择 `create_todo`。
- 看到“agent、工具、循环”，选择 `search_agent_notes`。
- 其他情况直接回答。

## `run_action()`

这个函数根据 `decision` 执行动作。

它使用白名单分发：

```python
if action == "make_learning_plan":
    ...
```

这样做是为了强调安全边界：Agent 不能随便执行任意代码，只能执行后端明确允许的动作。

## `build_final_answer()`

动作函数通常返回结构化结果。

例如学习计划动作返回：

```json
{
  "topic": "...",
  "plan": ["第一步", "第二步"]
}
```

`build_final_answer()` 负责把这些结构化结果整理成用户能读懂的回答。

## `run_minimal_agent()`

这是本模块最核心的函数。

它按顺序做四件事：

```text
1. 记录用户目标。
2. 调用 decide_action 思考下一步。
3. 调用 run_action 执行动作并得到观察结果。
4. 调用 build_final_answer 生成最终回答。
```

它返回：

- `reply`：最终回答。
- `is_agent`：说明这是 Agent 流程。
- `used_action`：是否执行了动作。
- `action`：动作名称。
- `steps`：中间步骤。

## `tools.py`

`tools.py` 里放了三个教学版动作：

- `search_agent_notes`
- `make_learning_plan`
- `create_todo`

这些动作不接真实数据库、不接真实模型、不接外部 API。

这样设计是为了让学习重点先放在 Agent 流程上，而不是环境配置。

## 当前模块的边界

这个模块还没有正式引入 tool schema。

它只是让你先知道：

```text
Agent 和普通聊天不一样，Agent 有目标、动作、观察和控制流程。
```

学完这里，再进入 `01_tool_calling`，就更容易理解为什么模型需要工具 schema。

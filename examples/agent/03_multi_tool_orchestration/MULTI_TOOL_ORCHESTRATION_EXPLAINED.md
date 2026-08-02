# 多工具编排代码讲解

## 1. main.py：接口入口

`main.py` 负责接收 HTTP 请求。

`AgentCaseRequest` 是请求体 DTO，类似 Java 里的 Request DTO。用户在 `/docs` 里填写的 JSON 会被 FastAPI 转成这个对象。

核心字段包括：

- `goal`：用户目标。
- `order_amount`：订单金额。
- `days_since_purchase`：购买后经过天数。
- `item_problem`：商品问题。
- `policy_keyword`：制度检索关键词。
- `stop_on_error`：工具失败后是否立刻停止。

`/agent/plan` 只调用 `build_plan()`，用于观察目标会被拆成哪些步骤。

`/agent/run` 调用 `run_orchestration()`，会真正执行工具并返回完整 `steps`。

## 2. planner.py：生成执行计划

`build_plan(case)` 接收一个普通字典 `case`。

这里的 `case` 来自：

```python
case = payload.model_dump()
```

`model_dump()` 是 Pydantic 的方法，会把 `AgentCaseRequest` 对象转成普通 Python 字典。

计划里的每个 step 都包含：

- `step_id`：步骤唯一名称。
- `tool_name`：要调用的工具。
- `arguments`：工具参数。
- `depends_on`：当前步骤依赖哪些前置步骤。
- `parallel_group`：教学用字段，提示哪些步骤理论上可并行。
- `why`：为什么安排这个步骤。

最关键的是 `from_step`：

```python
"policy": {"from_step": "policy", "field": "policy"}
```

它表示这个参数不是用户直接传进来的，而是从前面步骤的输出里取出来的。

## 3. orchestrator.py：执行编排

`run_orchestration(case)` 是本模块的核心。

它做四件事：

1. 调用 `build_plan(case)` 生成计划。
2. 按顺序遍历每个计划步骤。
3. 执行依赖检查和参数解析。
4. 调用工具并记录 steps。

这里用 `for` 循环执行计划：

```python
for step_number, planned_step in enumerate(plan["steps"], start=1):
```

`enumerate(..., start=1)` 会同时拿到序号和步骤内容。序号从 1 开始，更适合展示给学习者。

`step_outputs` 用来保存每个成功步骤的输出：

```python
step_outputs[step_id] = tool_result["data"]
```

后面的工具如果写了 `from_step`，就从 `step_outputs` 取数据。

## 4. 依赖检查如何工作

`has_failed_dependency()` 会检查当前步骤依赖的前置步骤是否都成功。

例如 `refund` 依赖：

```python
["policy", "risk"]
```

如果 `policy` 失败，`refund` 就会被记录为 `skipped`，不会继续执行。

这样做的好处是：错误会停在正确的位置，不会扩散成一串更难懂的参数错误。

## 5. 参数解析如何工作

`resolve_arguments()` 会把 planner 生成的参数转成工具真正需要的普通参数。

例如原始参数：

```python
{
    "policy": {"from_step": "policy", "field": "policy"}
}
```

会被解析成：

```python
{
    "policy": {
        "name": "7 天退款制度",
        "return_window_days": 7,
        "damaged_refund_rate": 1.0,
        "normal_refund_rate": 0.8
    }
}
```

如果字段名写错，`resolve_arguments()` 会抛出 `KeyError`，编排器会把当前步骤标记为 `failed`。

这正是多工具 Agent 里常见的“数据契约错误”。

## 6. tools.py：工具白名单

`run_tool()` 是唯一的工具执行入口。

它通过 `tool_name` 判断要调用哪个函数：

```python
if tool_name == "search_refund_policy":
    ...
elif tool_name == "evaluate_order_risk":
    ...
```

这样做是为了保留工具白名单。

模型或 planner 只能提出要调用哪个工具，真正是否允许执行，由后端代码决定。

## 7. 最终回答从哪里来

如果 `draft_customer_reply` 成功执行，它会输出：

```python
{
    "reply": "..."
}
```

`run_orchestration()` 会从 `step_outputs["reply"]["reply"]` 里取最终回答。

如果没有这个输出，说明前面某一步失败或跳过，最终状态就是 `failed`。

## 8. 本模块最重要的阅读顺序

建议按这个顺序读代码：

1. 先看 `main.py` 的请求体字段。
2. 再看 `planner.py` 的 steps 计划。
3. 再看 `orchestrator.py` 如何按计划执行。
4. 最后看 `tools.py` 每个工具具体做什么。

不要一开始就纠结真实大模型。先把“多个工具如何稳定协作”看懂，后面接入真实模型时才知道哪些地方必须约束和记录。

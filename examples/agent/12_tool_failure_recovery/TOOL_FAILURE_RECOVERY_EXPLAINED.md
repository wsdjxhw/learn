# 工具失败恢复代码讲解

这份文档只讲本模块新增链路，不重复权限和人工确认全部代码。

核心流程：

```text
工具执行请求
-> 权限检查
-> execute_tool_with_recovery()
-> run_tool() 单次执行
-> 可重试则重试
-> 多次失败则尝试 fallback
-> 返回 attempts 和失败解释
```

## 第一入口：`/tool/recovery-preview`

文件：

```text
main.py
```

函数：

```python
preview_tool_recovery()
```

这个接口专门用来学习失败恢复。它绕过 Agent 自动决策，但仍然保留：

- API Key 身份识别。
- 工具注册表查询。
- 权限检查。
- 恢复执行器。
- 审计日志。

读代码时重点看：

```python
tool_output = execute_tool_with_recovery(...)
```

这行把普通工具执行变成了可恢复执行。

## 核心文件：`recovery.py`

最重要函数：

```python
execute_tool_with_recovery()
```

它做 5 件事：

- 根据 `tool.max_retries` 计算最多尝试几次。
- 每次调用 `tools.py` 的 `run_tool()`。
- 如果返回 `retryable=True` 且还有次数，就继续重试。
- 如果多次失败且工具配置了 fallback，就调用降级工具。
- 最终返回稳定结构，包括 `attempts` 和 `failure_explanation`。

## 为什么 `_attempt` 是内部参数

`recovery.py` 每次调用工具前会复制参数：

```python
attempt_arguments = dict(arguments)
attempt_arguments["_attempt"] = attempt
```

`dict(arguments)` 是复制字典，避免污染原始请求体。

`_attempt` 是内部参数，用户不需要传。它让 mock 工具知道当前是第几次尝试，从而模拟“第 1 次失败，第 2 次成功”。

## 单次工具执行在哪里

文件：

```text
tools.py
```

函数：

```python
run_tool()
```

它只负责执行一次工具。

本模块新增：

```python
_simulate_teaching_failure()
```

支持：

- `simulate_failure=timeout`
- `simulate_failure=transient`
- `simulate_failure=permanent`

这些不是生产代码，而是教学开关，用来稳定观察失败恢复链路。

## 策略配置在哪里

文件：

```text
tool_registry.py
```

`ToolDefinition` 新增：

- `timeout_seconds`
- `max_retries`
- `fallback_tool_name`
- `expose_to_model`

`create_support_ticket` 配置为：

```text
max_retries = 2
fallback_tool_name = create_support_ticket_fallback
```

这表示主工具最多尝试 3 次，仍失败时尝试降级。

## 降级工具为什么不暴露给模型

`create_support_ticket_fallback` 有：

```text
expose_to_model = false
```

意思是：它是系统内部兜底工具，不应该让模型主动选择。

模型应该选择业务工具：

```text
create_support_ticket
```

系统执行器在失败后决定是否调用：

```text
create_support_ticket_fallback
```

这能避免模型绕过主流程。

## attempts 怎么读

一次响应里的 attempts 可能是：

```text
1 create_support_ticket timeout will_retry=true
2 create_support_ticket timeout will_retry=true
3 create_support_ticket timeout will_retry=false
4 create_support_ticket_fallback ok=true
```

你要看：

- `attempt`
- `tool_name`
- `ok`
- `error_code`
- `retryable`
- `will_retry`

这比只看最终结果更接近真实排查方式。

## 和确认单 approve 的关系

文件：

```text
confirmations.py
```

`approve_confirmation()` 里不再直接调用 `run_tool()`，而是调用：

```python
execute_tool_with_recovery(...)
```

这说明确认只是“允许执行”，不保证执行一定成功。

真实项目中，管理员批准后，外部系统仍然可能超时或失败。所以 approve 也必须走失败恢复策略。

## 如果要给新工具加恢复策略

一般改：

- `tool_registry.py`：配置 `max_retries`、`timeout_seconds`、`fallback_tool_name`。
- `tools.py`：保证失败返回 `error_code` 和 `retryable`。
- `recovery.py`：如果有新错误类型，在 `build_failure_explanation()` 中补解释。
- `README.md`：补测试命令。

不要把重试循环写在工具函数内部。工具函数只执行一次，恢复策略由统一执行器处理。

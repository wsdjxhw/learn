# 人工确认代码讲解

这份文档只讲本模块新增链路，不重复上一节全部权限代码。

先记住核心流程：

```text
权限检查通过
-> 判断工具是否需要人工确认
-> 创建 pending confirmation
-> approve 后才执行工具
-> reject 后不执行工具
-> 写审计日志
```

## 从 `/tool/run` 开始读

入口：

```text
main.py -> run_tool_manually()
```

上一模块里，权限通过后会直接调用：

```python
run_tool(...)
```

本模块在中间插入了一层：

```python
if should_require_confirmation(tool):
    create_pending_confirmation(...)
    return pending confirmation
```

这就是本节最重要的变化：高风险写工具不会在第一次请求里执行。

## 风险策略在哪里

文件：

```text
confirmations.py
```

函数：

```python
should_require_confirmation(tool)
```

它的规则是：

```text
tool.requires_confirmation 为 true
或者 tool_type=write 且 risk_level=high
```

注意：不是所有 high 风险工具都必须确认。例如 `list_audit_logs` 是 high，但它是管理员读工具，不是写工具，所以不需要确认。

## 工具如何标记需要确认

文件：

```text
tool_registry.py
```

`ToolDefinition` 新增了：

```python
requires_confirmation: bool = False
```

`update_user_plan` 被标记为：

```text
tool_type = write
risk_level = high
requires_confirmation = true
```

这让“风险含义”真正影响执行链路。

## 确认单怎么创建

文件：

```text
confirmations.py
```

函数：

```python
create_pending_confirmation()
```

它会保存：

- `confirmation_id`
- `request_id`
- 发起人身份
- 工具名
- 工具类型
- 风险等级
- 工具参数 JSON
- `status=pending`
- 需要确认的原因

创建确认单时不会调用 `run_tool()`。

## ORM 表在哪里

文件：

```text
models.py
```

核心类：

```python
PendingConfirmation
```

它是数据库表，不是接口返回 DTO。

最重要字段：

- `confirmation_id`：接口使用的确认单 ID。
- `arguments_json`：保存工具参数快照。
- `status`：确认单状态。
- `approver_user_id`：谁处理了确认单。
- `result_json`：批准后工具执行结果。
- `error`：执行失败原因。

## DTO 在哪里

文件：

```text
schemas.py
```

新增 DTO：

- `ConfirmationResponse`
- `ConfirmationApproveRequest`
- `ConfirmationRejectRequest`

`to_confirmation_response()` 会把 ORM Model 转成 DTO。这样前端看到的是稳定结构，而不是数据库内部对象。

## approve 链路怎么读

入口：

```text
main.py -> approve_pending_confirmation()
```

继续读：

```text
confirmations.py -> approve_confirmation()
```

它做 6 件事：

- 检查当前用户是不是 `admin`。
- 查确认单。
- 确认状态必须是 `pending`。
- 从 `arguments_json` 取出当时保存的工具参数。
- 调用 `run_tool()` 真正执行工具。
- 更新确认单状态，并写审计日志。

这条链路要精读。

## reject 链路怎么读

入口：

```text
main.py -> reject_pending_confirmation()
```

继续读：

```text
confirmations.py -> reject_confirmation()
```

它只更新状态，不执行工具。

重点是：

```text
reject 不应该调用 run_tool()
```

这是本模块最重要的安全边界之一。

## `/agent/chat` 有什么变化

上一模块里：

```text
Agent 选工具
-> 后端权限检查
-> 执行工具
-> final answer
```

本模块里：

```text
Agent 选高风险工具
-> 后端权限检查
-> 创建确认单
-> 返回 confirmation_required
```

所以 `/agent/chat` 的 `steps` 里会出现：

```text
confirmation_required
```

这代表 Agent 已经完成“发起危险操作”，但真正执行要等人工批准。

## `tools.py` 怎么变化

`update_user_plan()` 现在代表“确认后执行”。

它返回：

```text
status = updated_after_human_confirmation
```

如果你在第一次 `/tool/run` 就看到这个状态，说明确认层被绕过了，是 bug。

## 如果要给新工具加确认

一般改这些地方：

- `tool_registry.py`：设置 `requires_confirmation=True`。
- `confirmations.py`：如有参数级风险，在 `should_require_confirmation()` 补规则。
- `tools.py`：确保工具函数只表示“确认后执行”。
- `README.md`：补测试命令。

不要把确认逻辑写进工具函数内部。工具函数应该专注执行，是否需要确认应该由确认层统一控制。

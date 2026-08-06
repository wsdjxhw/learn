# 12 工具失败和恢复策略

本模块解决的问题：真实 Agent 工具不是总能成功。外部系统可能超时、网络抖动、参数不合法、业务规则拒绝。后端不能让工具失败直接把接口打崩，也不能盲目无限重试。

本模块是独立可运行模块，但代码基于 `11_human_confirmation` 演进。它保留工具权限、人工确认和审计日志，在此基础上新增“失败恢复执行器”。

## 学习目标

学完本模块，你应该能讲清楚：

- 为什么工具失败不能只返回 `500`。
- 哪些失败适合重试，哪些失败不应该重试。
- 超时、短暂失败、永久失败的处理差异。
- 降级工具什么时候有价值，什么时候会掩盖真实问题。
- 为什么每次尝试都要记录 attempt、耗时、错误码和是否继续重试。

你应该能做：

- 给工具配置 `timeout_seconds`、`max_retries`、`fallback_tool_name`。
- 让工具失败时返回稳定结构，而不是让接口崩溃。
- 看懂一次工具调用尝试了几次、为什么重试、最后是否降级。
- 在确认单 approve 后也复用同一套失败恢复策略。

## 和上一模块的关系

本模块继承：

- API Key 认证。
- 工具注册表和权限检查。
- 资源级权限和参数级权限。
- 高风险工具人工确认。
- 确认单状态流转。
- 工具审计日志。
- mock / DeepSeek 双模式。

本模块新增：

- `recovery.py`：统一工具恢复执行器。
- `ToolDefinition.timeout_seconds`
- `ToolDefinition.max_retries`
- `ToolDefinition.fallback_tool_name`
- `ToolDefinition.expose_to_model`
- `/tool/recovery-preview` 专门观察失败恢复。
- `simulate_failure` 教学参数，用来稳定模拟超时、短暂失败、永久失败。
- 降级工具 `create_support_ticket_fallback`。

## 启动方式

```bash
cd examples/agent/12_tool_failure_recovery
pip install -r requirements.txt
uvicorn main:app --reload --port 8013
```

打开：

```text
http://127.0.0.1:8013/docs
```

默认 mock 模式，不需要真实模型 API Key。

## 教学 API Key

```text
learner-key   -> viewer
operator-key  -> operator
admin-key     -> admin
```

请求头：

```text
X-API-Key
```

## 接口测试顺序

### 1. 确认服务启动

```bash
curl http://127.0.0.1:8013/health
```

要看到：

```text
module = 12_tool_failure_recovery
model_mode = mock
```

### 2. 查看工具恢复配置

```bash
curl -H "X-API-Key: operator-key" "http://127.0.0.1:8013/tools?include_forbidden=true"
```

重点看 `create_support_ticket`：

```text
timeout_seconds = 1.0
max_retries = 2
fallback_tool_name = create_support_ticket_fallback
```

`create_support_ticket_fallback` 的 `expose_to_model=false`，说明它是内部降级工具，不应该让模型主动选择。

### 3. 正常执行工具

```bash
curl -X POST http://127.0.0.1:8013/tool/recovery-preview ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"tool_name\":\"create_support_ticket\",\"arguments\":{\"target_user_id\":\"u_operator\",\"title\":\"登录失败需要处理\",\"priority\":\"normal\"}}"
```

你要看：

- `recovery_action=none`
- `attempts` 只有 1 次
- `tool_output.ok=true`

### 4. 模拟短暂失败后重试成功

```bash
curl -X POST http://127.0.0.1:8013/tool/recovery-preview ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"tool_name\":\"create_support_ticket\",\"arguments\":{\"target_user_id\":\"u_operator\",\"title\":\"登录失败需要处理\",\"priority\":\"normal\",\"simulate_failure\":\"transient\",\"fail_times\":1}}"
```

你要看：

- 第 1 次 `ok=false`
- 第 1 次 `will_retry=true`
- 第 2 次 `ok=true`
- `recovery_action=retried`

### 5. 模拟超时后走降级工具

可以用 `simulate_failure=timeout` 直接模拟超时，也可以传 `requested_delay_seconds=2`，让执行器根据 `timeout_seconds=1.0` 判定超时。

```bash
curl -X POST http://127.0.0.1:8013/tool/recovery-preview ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"tool_name\":\"create_support_ticket\",\"arguments\":{\"target_user_id\":\"u_operator\",\"title\":\"登录失败需要处理\",\"priority\":\"normal\",\"simulate_failure\":\"timeout\"}}"
```

你要看：

- 主工具尝试 3 次。
- 最后调用 `create_support_ticket_fallback`。
- `recovery_action=fallback_used`
- `fallback_used=true`

### 6. 模拟永久失败

```bash
curl -X POST http://127.0.0.1:8013/tool/recovery-preview ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"tool_name\":\"create_support_ticket\",\"arguments\":{\"target_user_id\":\"u_operator\",\"title\":\"登录失败需要处理\",\"priority\":\"normal\",\"simulate_failure\":\"permanent\"}}"
```

你要看：

- 不会重试。
- 不会降级。
- `recovery_action=failed`
- `failure_explanation` 说明继续重试通常无效。

### 7. 验证确认单 approve 也会走恢复策略

高优先级工单会先进入人工确认：

```bash
curl -X POST http://127.0.0.1:8013/tool/run ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"tool_name\":\"create_support_ticket\",\"arguments\":{\"target_user_id\":\"u_operator\",\"title\":\"高优先级登录故障\",\"priority\":\"high\",\"simulate_failure\":\"transient\",\"fail_times\":1}}"
```

复制 `confirmation_id`，然后管理员批准：

```bash
curl -X POST http://127.0.0.1:8013/confirmations/CONF_xxx/approve ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: admin-key" ^
  -d "{\"reason\":\"高优先级故障已核对\"}"
```

你要看：

- 确认单 `status=executed`
- `result.tool_output.recovery_action=retried`
- `attempts` 有 2 次

## 代码阅读路线

必须精读：

- `main.py`：`/tool/recovery-preview`、`/tool/run`、`/agent/chat`。
- `recovery.py`：本模块核心，重试、降级、失败解释都在这里。
- `tools.py`：`simulate_failure` 如何制造稳定故障。
- `tool_registry.py`：工具超时、重试次数、降级工具配置。
- `confirmations.py`：approve 后如何复用恢复执行器。

可以粗读：

- `permissions.py`：上一模块能力，确认执行前仍然要先过权限。
- `models.py`：本模块复用确认单和审计日志表。
- `provider.py`：mock / DeepSeek 工具选择。
- `database.py`、`settings.py`：配置和数据库入口。

暂时不用管：

- 真正的异步超时取消。
- 指数退避和抖动。
- 熔断器。
- 分布式队列。
- 统一 tracing 平台。

如果只有 30 分钟，只看这一条链路：

```text
POST /tool/recovery-preview
-> main.py preview_tool_recovery()
-> check_tool_permission()
-> recovery.py execute_tool_with_recovery()
-> tools.py run_tool()
-> recovery.py build_failure_explanation()
-> write_tool_audit_log()
```

## 真实项目通常怎么做

真实项目一般会：

- 给外部 HTTP 工具设置硬超时。
- 对网络抖动、限流、临时不可用做有限重试。
- 对参数错误、权限错误、业务拒绝不重试。
- 重试使用指数退避和随机抖动，避免雪崩。
- 主路径失败后写入队列、缓存或人工处理系统作为降级。
- 记录每次 attempt 的耗时、错误码、是否重试。
- 把失败解释返回给用户和前端，而不是只暴露堆栈。

## 教学版做了哪些简化

- 没有真正 sleep 或取消线程，用 `simulate_failure` 稳定模拟故障。
- 没有指数退避，只做固定次数重试。
- 没有真正外部工单系统，用 mock 字典返回结果。
- 降级工具只是返回 `queued_for_manual_retry`。
- 没有分布式 trace，只把 attempts 放进接口响应和审计日志。

## 本模块 5 个核心知识点

- 工具执行要区分可重试错误和不可重试错误。
- 重试必须有上限，不能无限循环。
- 降级只能用于适合兜底的失败，不能掩盖永久业务错误。
- 每次 attempt 都要结构化记录。
- Agent 最终回答要能解释失败和下一步建议。

## 面试和真实开发能讲什么

你可以这样讲：

> 我把工具调用封装成统一的恢复执行器。工具本身只执行一次，执行器负责根据工具注册表里的超时、最大重试次数和降级工具决定下一步。短暂错误会有限重试，超时多次失败后进入降级工具，永久业务错误不会重试也不会降级。每次尝试都会记录 attempt、耗时、错误码和是否继续重试，最终返回稳定结构给前端和审计日志。

## 练习任务

### 练习 1：给重试增加退避时间字段

要求：不需要真的 sleep，但要在 attempts 里返回 `next_retry_after_ms`。

真实能力：理解生产系统为什么不能失败后立刻疯狂重试。

### 练习 2：让永久失败跳过降级，并解释原因

要求：确认 `permanent_error` 不调用 fallback，并在 `failure_explanation` 中说明“业务错误重试无效”。

真实能力：练习区分技术故障和业务失败。

### 练习 3：给 `get_user_plan` 配置只重试一次

要求：让它支持 `simulate_failure=transient`，并配置 `max_retries=1`。

真实能力：不同工具的重试策略不应该完全一样。

### 练习 4：在 `/agent/chat` 的 steps 里展示 attempts 摘要

要求：工具失败或重试时，`steps` 中要能看出每次尝试的结果。

真实能力：为后续前端工作台和可观测性模块做准备。

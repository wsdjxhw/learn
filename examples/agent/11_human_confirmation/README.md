# 11 危险操作和人工确认

本模块解决的问题：在真实 Agent 项目里，“用户有权限”不等于“系统可以立刻执行危险操作”。修改套餐、删除数据、发邮件、付款、写数据库这类操作，即使权限检查通过，也应该先生成待确认操作，由人批准后再真正执行。

本模块是独立可运行模块，但代码基于上一节 `10_tool_permissions` 演进。你不需要重新学习整套权限代码，本节只重点看“确认单状态流转”。

## 学习目标

学完本模块，你应该能讲清楚：

- 为什么高风险写工具不能只靠角色权限控制。
- `pending -> executed/rejected/failed` 状态流转解决什么工程问题。
- Agent 为什么只能创建待确认操作，不能直接执行危险动作。
- 批准和拒绝为什么都要写审计日志。
- 确认单、工具审计日志、工具执行结果之间是什么关系。

你应该能做：

- 给一个工具标记 `requires_confirmation=True`。
- 在工具权限通过后创建 pending confirmation，而不是直接执行。
- 实现 approve 后执行工具，reject 后不执行工具。
- 查询确认单和审计日志，解释一次危险操作发生了什么。

## 和上一模块的关系

代码复用方式：

```text
10_tool_permissions 是基线
11_human_confirmation 是在基线上的独立拷贝和增量修改
```

本模块继承：

- API Key 认证。
- `viewer/operator/admin` 角色。
- 工具注册表。
- 工具权限检查。
- 资源级权限。
- 工具审计日志。
- mock / DeepSeek 双模式。

本模块新增：

- `PendingConfirmation` 确认单表。
- `requires_confirmation` 工具元数据。
- `should_require_confirmation()` 风险策略。
- `/confirmations` 查询确认单。
- `/confirmations/{id}/approve` 批准并执行。
- `/confirmations/{id}/reject` 拒绝且不执行。

## 启动方式

进入本模块目录：

```bash
cd examples/agent/11_human_confirmation
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn main:app --reload --port 8011
```

Copy-Item .env.example .env

打开接口文档：

```text
http://127.0.0.1:8011/docs
```

默认 `MODEL_MODE=mock`，没有 API Key 也能跑通。

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

不传 `X-API-Key` 时，教学版默认使用 `learner-key`。真实项目不应这样做。

## 接口测试顺序

### 1. 确认服务启动

```bash
curl http://127.0.0.1:8011/health
```

要看：

- `module=11_human_confirmation`
- `model_mode=mock`

### 2. 查看工具列表

```bash
curl -H "X-API-Key: admin-key" "http://127.0.0.1:8011/tools?include_forbidden=true"
```

重点看 `update_user_plan`：

```text
risk_level = high
tool_type = write
requires_confirmation = true
```

### 3. 直接请求高风险工具

```bash
curl -X POST http://127.0.0.1:8011/tool/run ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: admin-key" ^
  -d "{\"tool_name\":\"update_user_plan\",\"arguments\":{\"target_user_id\":\"u_learner\",\"new_plan\":\"pro\",\"reason\":\"用户申请升级\"}}"
```

你应该看到：

- `requires_confirmation=true`
- `confirmation.status=pending`
- 工具没有真正返回 `updated_after_human_confirmation`

### 4. 查看待确认单

```bash
curl -H "X-API-Key: admin-key" "http://127.0.0.1:8011/confirmations?status=pending"
```

复制返回里的 `confirmation_id`。

### 5. 批准确认单

```bash
curl -X POST http://127.0.0.1:8011/confirmations/CONF_xxx/approve ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: admin-key" ^
  -d "{\"reason\":\"已核对用户申请和套餐信息\"}"
```

你应该看到：

- `status=executed`
- `executed_at` 有时间
- `result.tool_output.result.status=updated_after_human_confirmation`

### 6. 验证拒绝不会执行

先再次创建一个确认单，再调用：

```bash
curl -X POST http://127.0.0.1:8011/confirmations/CONF_xxx/reject ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: admin-key" ^
  -d "{\"reason\":\"缺少用户确认材料\"}"
```

你应该看到：

- `status=rejected`
- `executed_at=null`
- 工具没有执行结果。

### 7. 查看审计日志

```bash
curl -H "X-API-Key: admin-key" "http://127.0.0.1:8011/audit/logs?limit=20"
```

重点看三类日志：

- 创建待确认单。
- 批准后执行工具。
- 拒绝后未执行工具。

### 8. 通过 Agent 自动触发确认

```bash
curl -X POST http://127.0.0.1:8011/agent/chat ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: admin-key" ^
  -d "{\"message\":\"帮用户升级套餐到专业版\",\"allow_tool\":true}"
```

重点看 `steps`：

- `visible_tools`
- `model_decision`
- `confirmation_required`

## 代码阅读路线

必须精读：

- `main.py`：`/tool/run`、`/agent/chat`、`/confirmations/{id}/approve`、`/confirmations/{id}/reject`。
- `confirmations.py`：本模块核心，创建、查询、批准、拒绝确认单。
- `models.py`：`PendingConfirmation` 表结构。
- `schemas.py`：确认单相关 DTO。
- `tool_registry.py`：`requires_confirmation` 如何标记危险工具。

可以粗读：

- `permissions.py`：上一模块能力，知道权限检查仍在执行前发生即可。
- `tools.py`：只重点看 `update_user_plan()`，它现在代表“确认后执行”。
- `provider.py`：mock / DeepSeek 如何选择工具。
- `database.py`、`settings.py`：沿用上一模块结构。

暂时不用管：

- 分布式审批流。
- 多级审批。
- 幂等键、回滚、补偿事务。
- 前端审批工作台。这些后面会逐步进入完整项目。

如果只有 30 分钟，只看这一条链路：

```text
POST /tool/run
-> main.py run_tool_manually()
-> check_tool_permission()
-> should_require_confirmation()
-> create_pending_confirmation()
-> POST /confirmations/{id}/approve
-> approve_confirmation()
-> tools.py run_tool()
-> write_tool_audit_log()
```

## 真实项目通常怎么做

真实项目一般会：

- 按风险等级决定是否需要人工确认。
- 确认单里保存操作快照，避免用户批准时参数被偷偷改掉。
- 危险操作批准后使用幂等键，避免重复点击导致重复执行。
- 发起人和批准人可能必须不是同一个人。
- 确认单会有过期时间，超时自动取消。
- 审计日志会进入统一 trace 系统，关联用户、请求、工具、确认单和执行结果。

## 教学版做了哪些简化

- 只有 `admin` 可以批准或拒绝。
- 没有强制“发起人和批准人不能相同”。
- 没有确认单过期时间。
- 没有真正修改外部业务系统，只用 mock 返回值模拟执行。
- 没有做幂等键和事务补偿。

## 本模块 5 个核心知识点

- 权限通过不等于危险操作可以立刻执行。
- 确认单保存的是“准备执行的操作快照”。
- `pending/executed/rejected/failed` 是危险操作的最小状态机。
- approve 后才执行工具，reject 后绝不执行工具。
- 确认记录和工具审计日志要能互相追踪。

## 面试和真实开发能讲什么

你可以这样讲：

> 我把 Agent 工具调用分成权限检查和人工确认两层。普通工具权限通过后可直接执行；高风险写工具即使权限通过，也只创建 pending confirmation，保存工具名、参数、发起人和风险等级。管理员批准后才执行工具，并把确认结果和工具执行结果写入审计日志；拒绝时不执行工具，也记录拒绝原因。

## 练习任务

### 练习 1：给确认单增加过期时间

要求：新增 `expires_at` 字段，超过时间后不能 approve，只能返回 409。

真实能力：危险操作不能无限期等待，否则旧参数可能在未来被误批准。

### 练习 2：禁止发起人批准自己的确认单

要求：如果 `approver.user_id == requester_user_id`，返回 403。

真实能力：练习职责分离。真实项目中，高风险操作常要求第二个人确认。

### 练习 3：给 `create_support_ticket` 也加确认

要求：当 `priority=high` 时需要确认；普通优先级仍直接执行。

真实能力：练习参数级风险判断，不是整个工具永远同一风险。

### 练习 4：处理重复批准

要求：同一个确认单 approve 两次，第二次必须返回 409，且不会重复执行工具。

真实能力：练习幂等和状态机边界。

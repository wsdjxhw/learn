# 10 工具设计和权限

本模块解决的问题：Agent 不是只能“回答”，它会调用工具读资料、查用户、创建工单、修改业务数据。真实项目里，模型不能想调什么就调什么，后端必须有工具注册表、角色权限、资源级权限和审计日志。

你这一节不是学“怎么多写几个工具”，而是学会把工具调用变成可控的企业级后端能力。

## 学习目标

学完本模块，你应该能讲清楚：

- 工具注册表为什么是 Agent 后端的白名单，而不是普通配置列表。
- 读工具、写工具、管理员工具的风险差异。
- 为什么“只把允许的工具 schema 给模型”还不够，后端执行前仍要再做权限检查。
- API Key / 用户角色 / 资源归属三层权限分别解决什么问题。
- 为什么工具成功、失败、越权都要写审计日志。

你应该能做：

- 新增一个工具，并把 schema、权限、执行函数、审计链路接起来。
- 让普通用户、操作员、管理员看到不同工具。
- 解释一次工具调用从 HTTP 请求到权限判断、执行、审计、返回的完整链路。
- 在面试中说明如何防止 Agent 被 prompt injection 诱导调用未授权工具。

## 启动方式

进入本模块目录：

```bash
cd examples/agent/10_tool_permissions
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn main:app --reload --port 8010
```

打开接口文档：

```text
http://127.0.0.1:8010/docs
```

默认是 mock 模式，不需要任何真实模型 API Key。

## 教学 API Key

本模块用 3 个教学 API Key 模拟不同身份：

```text
learner-key   -> viewer   普通用户
operator-key  -> operator 运营/客服操作员
admin-key     -> admin    管理员
```

请求头名称：

```text
X-API-Key
```

如果不传 `X-API-Key`，教学版默认使用 `learner-key`。真实项目不能这样做，生产环境应该缺少 Key 就返回 401。

## 接口测试顺序

### 1. 先确认服务和身份

```bash
curl http://127.0.0.1:8010/health
```

```bash
curl -H "X-API-Key: learner-key" http://127.0.0.1:8010/auth/whoami
```

你要看：

- `model_mode` 是否是 `mock`。
- 当前 API Key 被识别成什么 `role`。

### 2. 查看当前用户能看到哪些工具

普通用户：

```bash
curl -H "X-API-Key: learner-key" "http://127.0.0.1:8010/tools"
```

管理员：

```bash
curl -H "X-API-Key: admin-key" "http://127.0.0.1:8010/tools"
```

对比重点：

- 普通用户只能看到低风险读工具。
- 管理员能看到高风险写工具和审计工具。

查看“包括无权工具”的完整权限解释：

```bash
curl -H "X-API-Key: learner-key" "http://127.0.0.1:8010/tools?include_forbidden=true"
```

### 3. 手动执行一个普通读工具

```bash
curl -X POST http://127.0.0.1:8010/tool/run ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: learner-key" ^
  -d "{\"tool_name\":\"search_company_policy\",\"arguments\":{\"keyword\":\"报销\"}}"
```

你要看：

- `allowed=true`
- `permission_reason=权限检查通过`
- `tool_output.ok=true`

### 4. 故意让普通用户调用管理员工具

```bash
curl -X POST http://127.0.0.1:8010/tool/run ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: learner-key" ^
  -d "{\"tool_name\":\"update_user_plan\",\"arguments\":{\"target_user_id\":\"u_learner\",\"new_plan\":\"pro\",\"reason\":\"测试越权\"}}"
```

你应该看到 403 错误。重点不是“失败”，而是失败原因要清楚，并且审计日志里能查到这次越权尝试。

### 5. 用管理员执行高风险工具

```bash
curl -X POST http://127.0.0.1:8010/tool/run ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: admin-key" ^
  -d "{\"tool_name\":\"update_user_plan\",\"arguments\":{\"target_user_id\":\"u_learner\",\"new_plan\":\"pro\",\"reason\":\"用户申请升级\"}}"
```

本模块允许管理员执行，但下一模块会继续加入“高风险写操作必须人工确认”。

### 6. 查看审计日志

```bash
curl -H "X-API-Key: admin-key" "http://127.0.0.1:8010/audit/logs?limit=20"
```

你要看：

- 成功调用有日志。
- 工具执行失败有日志。
- 权限拒绝也有日志。

### 7. 运行 Agent 自动选工具

```bash
curl -X POST http://127.0.0.1:8010/agent/chat ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"message\":\"帮我创建一个客服工单，用户说登录失败\",\"allow_tool\":true}"
```

你要看 `steps`：

- `visible_tools`
- `model_decision`
- `tool_execution`
- `final_answer`

## 代码阅读路线

不要从第一个文件第一行读到最后一个文件最后一行。按链路读。

必须精读：

- `main.py`：接口入口，尤其是 `/tool/run` 和 `/agent/chat`。
- `permissions.py`：API Key 识别、角色权限、资源级权限、审计写入。
- `tool_registry.py`：工具注册表、工具类型、风险等级、OpenAI 工具 schema。
- `tools.py`：工具执行入口 `run_tool()`，看它如何避免动态执行未知函数。
- `schemas.py`：DTO，理解请求体、响应体和 ORM Model 的区别。

可以粗读：

- `provider.py`：mock 决策和 DeepSeek 决策如何选择工具。
- `database.py`：SQLAlchemy 会话和建表逻辑，前面模块已经学过。
- `models.py`：只需要看 `ToolAuditLog` 字段，不需要背 SQLAlchemy 语法。
- `settings.py`：配置从 `.env` 读取，知道有哪些环境变量即可。

暂时不用管：

- DeepSeek 真实工具调用细节。没有 Key 时先用 mock 抓住权限链路。
- 更复杂的确认流、回滚、事务一致性。下一模块开始处理危险操作确认。

如果只有 30 分钟，只看这一条链路：

```text
POST /tool/run
-> main.py run_tool_manually()
-> permissions.py get_current_auth()
-> tool_registry.py get_tool_definition()
-> permissions.py check_tool_permission()
-> tools.py run_tool()
-> permissions.py write_tool_audit_log()
-> schemas.py ToolRunResponse
```

## 真实项目通常怎么做

真实项目一般会：

- 用数据库或配置中心管理工具注册表，支持上下线和灰度。
- API Key 只负责认证，权限来自用户、组织、角色、套餐、资源归属等多层数据。
- 只把当前用户可用工具传给模型，但工具执行前仍然做后端权限检查。
- 对写工具、高风险工具加入人工确认、幂等键、事务、回滚或补偿。
- 所有工具调用写 trace / audit / cost 日志，方便排查和合规。

## 教学版做了哪些简化

- API Key 固定写在 `.env.example`，不接真实账号系统。
- 工具数据大多是 mock，不调用真实业务系统。
- 写工具只返回教学结果，主要靠审计日志展示“写操作发生过”。
- 权限模型只分 `viewer/operator/admin` 三档，没有组织、部门、套餐等复杂规则。
- 高风险写工具暂时只做权限控制，人工确认放到下一模块。

## 本模块 5 个核心知识点

- 工具注册表：后端可执行工具的唯一白名单。
- 工具权限：角色权限决定能不能调用某类工具。
- 资源级权限：能调用工具不等于能操作别人的数据。
- 读写风险边界：读工具也可能泄露数据，写工具可能改变业务状态。
- 审计日志：成功、失败、越权都要记录。

## 和前后模块的衔接

复用前面能力：

- `01_tool_calling` 的工具 schema 和工具执行思想。
- `07_short_term_state` 的 steps 思路，用来展示 Agent 中间过程。
- `09_memory_governance` 的治理意识：不是所有模型想保存或调用的内容都应该被允许。
- SQLAlchemy / DTO / 依赖注入等后端基础。

为后面准备：

- `11_human_confirmation` 会在本模块权限基础上处理危险写操作确认。
- `12_tool_failure_recovery` 会处理工具失败、超时、重试和降级。
- `15_database_tool_agent` 会把权限控制应用到真实数据库读写工具。
- `22_agent_safety` 会进一步处理 prompt injection 和越权工具调用。

## 练习任务

### 练习 1：给 `search_company_policy` 增加参数级权限

要求：新增一个制度关键词 `薪酬`，但只有 `admin` 可以查询；`viewer/operator` 查询 `薪酬` 时返回 403，并写入审计日志。

真实能力：练习“能调用某个工具”不代表“能用这个工具查所有内容”。真实项目里，同一个检索工具也可能按关键词、文档密级、部门权限继续过滤。

验收：`viewer-key` 不存在，应该使用 `learner-key` 测试普通用户；`learner-key` 查 `薪酬` 返回 403，`admin-key` 查 `薪酬` 成功。

### 练习 2：新增一个中风险读工具 `get_user_plan`

要求：

- 在 `tool_registry.py` 注册工具。
- 在 `tools.py` 实现工具。
- `viewer` 只能查自己，`operator/admin` 可以查自己，只有 `admin` 可以查别人。
- `/tools` 能看到权限差异。

真实能力：新增工具时要同时考虑 schema、执行逻辑、权限和审计。

### 练习 3：让高风险写工具返回“需要确认”

要求：把 `update_user_plan` 的直接执行改成返回 `requires_confirmation=true`，不要真正执行。

真实能力：为下一模块做准备，理解危险操作不能只靠角色权限。

验收：管理员调用该工具时不返回 `status=updated_in_teaching_mock`，而是返回待确认结构。

### 练习 4：排查一次越权调用

要求：先用 `learner-key` 调用 `update_user_plan`，再用 `admin-key` 查看 `/audit/logs`，说明日志里哪些字段能帮助定位问题。

真实能力：练习生产排查，而不是只看接口返回。

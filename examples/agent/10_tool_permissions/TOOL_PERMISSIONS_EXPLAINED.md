# 工具权限代码讲解

这份文档按核心链路解释代码，不逐行背语法。

建议先跑 `/tool/run`，再回来看代码。你要建立的是链路感：

```text
HTTP 请求
-> 当前用户是谁
-> 工具是否注册
-> 当前用户能不能调用
-> 参数是否允许操作目标资源
-> 执行工具
-> 写审计日志
-> 返回稳定响应
```

## 第一条链路：手动执行工具

入口：

```text
POST /tool/run
```

先看 `main.py` 里的 `run_tool_manually()`。

它做 5 件事：

- 从请求体拿到 `tool_name` 和 `arguments`。
- 通过 `get_current_auth()` 拿到当前用户身份。
- 从 `tool_registry.py` 查工具定义。
- 调用 `check_tool_permission()` 做权限判断。
- 调用 `tools.py` 的 `run_tool()` 执行工具，并写审计日志。

这里最重要的不是工具本身，而是执行前后的保护层。

## 身份从哪里来

文件：

```text
permissions.py
```

函数：

```python
get_current_auth()
```

`x_api_key: str | None = Header(default=None, alias="X-API-Key")` 表示 FastAPI 会从 HTTP 请求头读取 `X-API-Key`。

这个值不是用户在 JSON 请求体里传的，而是请求头传的。

教学版把不同 Key 映射成不同角色：

```text
learner-key  -> viewer
operator-key -> operator
admin-key    -> admin
```

返回值是 `AuthContext` DTO，后续业务函数都用它判断权限。

## 工具注册表怎么读

文件：

```text
tool_registry.py
```

核心对象：

```python
TOOL_REGISTRY
```

它保存每个工具的：

- `name`
- `description`
- `tool_type`
- `risk_level`
- `allowed_roles`
- `enabled`

`ToolDefinition.to_openai_tool_schema()` 会把工具定义转换成 OpenAI 兼容的 tool schema，供 DeepSeek 模型选择工具。

注意：schema 只是给模型看的说明书，不是权限系统。

## 权限检查在哪里

文件：

```text
permissions.py
```

函数：

```python
check_tool_permission()
```

它先检查角色：

```text
auth.role 是否在 tool.allowed_roles 里
```

再检查资源归属：

```text
arguments.target_user_id 是否等于 auth.user_id
```

如果不是本人资源，除非是 `admin`，否则拒绝。

这一步非常关键。很多真实系统的越权漏洞不是“普通用户调用了管理员接口”，而是“有权限调用接口的人操作了不属于自己的数据”。

## 工具执行在哪里

文件：

```text
tools.py
```

核心入口：

```python
run_tool(tool_name, arguments, db)
```

它用明确的 `if/elif` 分发工具，而不是用 `globals()` 动态调用函数。

原因是：模型输出不可信。如果模型生成了一个不存在或危险的函数名，后端不能直接执行。

你应该重点看 3 个工具：

- `search_company_policy()`：低风险读工具。
- `create_support_ticket()`：中风险写工具。
- `update_user_plan()`：高风险写工具。

## 审计日志在哪里写

文件：

```text
permissions.py
```

函数：

```python
write_tool_audit_log()
```

它写入 `models.py` 里的 `ToolAuditLog`。

重点字段：

- `request_id`：关联一次工具调用。
- `user_id` / `role` / `api_key_name`：谁调用。
- `tool_name` / `tool_type` / `risk_level`：调了什么工具。
- `allowed` / `reason`：权限判断结果。
- `arguments_json`：工具入参。
- `result_json` / `error`：执行结果或失败原因。

权限拒绝时也会写日志，这是企业级系统必须具备的排查能力。

## 第二条链路：Agent 自动选工具

入口：

```text
POST /agent/chat
```

先看 `main.py` 的 `agent_chat()`。

它先根据当前用户权限过滤可见工具：

```text
list_tool_definitions()
-> check_tool_permission()
-> tool.to_openai_tool_schema()
```

然后把可见工具交给 `provider.py`：

```text
decide_next_action()
```

mock 模式里，模型决策由关键词模拟。DeepSeek 模式里，通过 `openai` Python 包传入 tools 参数，让模型选择工具。

即使工具来自“可见工具列表”，后端仍然再次调用 `check_tool_permission()`。这是防御式设计：模型层能过滤，执行层必须兜底。

## DTO 怎么跟着链路走

文件：

```text
schemas.py
```

你需要精读这些 DTO：

- `AuthContext`：当前调用者身份。
- `ToolRunRequest`：手动执行工具的请求体。
- `ToolRunResponse`：工具执行接口返回体。
- `ChatRequest` / `ChatResponse`：Agent 自动选工具接口。
- `ToolInfo`：`/tools` 展示用结构。

DTO 的作用是稳定接口契约。前端和调用方不应该直接依赖 ORM Model。

## 数据库代码怎么读

文件：

```text
database.py
models.py
```

本模块只有一张表：

```text
tool_audit_logs
```

你只要理解：

- `ToolAuditLog` 是 ORM Model，会映射成数据库表。
- `init_db()` 启动时创建表。
- `get_db()` 通过依赖注入给接口函数提供 `Session`。
- `db.add()` 添加对象。
- `db.commit()` 提交事务。
- `db.refresh()` 刷新数据库生成的字段，例如自增 ID。

## DeepSeek 路径怎么看

文件：

```text
provider.py
```

真实模型路径只在 `MODEL_MODE=deepseek` 时启用。

它使用：

```python
OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
```

这表示通过 openai Python 包的 OpenAI 兼容协议调用 DeepSeek。

学习本模块时，不建议一开始就看真实模型调用细节。先用 mock 模式理解权限链路，再看真实模型如何接入。

## 如果要新增工具，应该改哪些文件

新增一个工具通常要改：

- `tool_registry.py`：注册工具元数据和参数 schema。
- `tools.py`：实现工具函数，并接入 `run_tool()` 分发。
- `permissions.py`：如果有特殊资源级权限，在这里补规则。
- `schemas.py`：如果接口响应需要新 DTO，才改这里。
- `README.md`：补测试命令和学习说明。

不要只在 `tools.py` 写一个函数就结束。真实项目里，工具没有注册、没有权限、没有审计，就不能算可用工具。

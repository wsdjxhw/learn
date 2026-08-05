# 先从这里开始

如果你时间有限，按这个顺序学：

1. 启动服务：`uvicorn main:app --reload --port 8010`
2. 打开 `/docs`
3. 跑 `/auth/whoami`，分别传 `learner-key`、`operator-key`、`admin-key`
4. 跑 `/tools?include_forbidden=true`，看同一批工具对不同角色的权限差异
5. 跑 `/tool/run`，先成功调用 `search_company_policy`
6. 再用 `learner-key` 越权调用 `update_user_plan`
7. 最后用 `admin-key` 查看 `/audit/logs`

30 分钟只看一条代码链路：

```text
main.py run_tool_manually()
-> permissions.py get_current_auth()
-> tool_registry.py get_tool_definition()
-> permissions.py check_tool_permission()
-> tools.py run_tool()
-> permissions.py write_tool_audit_log()
```

本节最重要的一句话：

```text
模型只能建议调用工具，后端必须决定能不能执行。
```

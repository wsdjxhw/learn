# 先从这里开始

如果只想用 30 分钟抓住本节核心，按这个顺序：

1. 启动：`uvicorn main:app --reload --port 8011`
2. 打开：`http://127.0.0.1:8011/docs`
3. 用 `admin-key` 调 `/tools?include_forbidden=true`
4. 确认 `update_user_plan` 的 `requires_confirmation=true`
5. 用 `/tool/run` 发起 `update_user_plan`
6. 复制返回的 `confirmation_id`
7. 调 `/confirmations/{confirmation_id}/approve`
8. 再看 `/audit/logs`

只读这条链路：

```text
main.py run_tool_manually()
-> confirmations.py should_require_confirmation()
-> confirmations.py create_pending_confirmation()
-> main.py approve_pending_confirmation()
-> confirmations.py approve_confirmation()
-> tools.py run_tool()
```

本节最重要的一句话：

```text
有权限发起危险操作，不等于可以立刻执行危险操作。
```

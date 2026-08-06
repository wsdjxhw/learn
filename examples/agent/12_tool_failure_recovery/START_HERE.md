# 先从这里开始

如果只想用 30 分钟抓住本节核心，按这个顺序：

1. 启动：`uvicorn main:app --reload --port 8013`
2. 打开：`http://127.0.0.1:8013/docs`
3. 用 `operator-key` 调 `/tools?include_forbidden=true`
4. 找到 `create_support_ticket` 的 `max_retries` 和 `fallback_tool_name`
5. 调 `/tool/recovery-preview`，先正常创建工单
6. 再传 `simulate_failure=transient`
7. 再传 `simulate_failure=timeout`
8. 最后传 `simulate_failure=permanent`

只读这条链路：

```text
main.py preview_tool_recovery()
-> recovery.py execute_tool_with_recovery()
-> tools.py run_tool()
-> recovery.py build_failure_explanation()
```

本节最重要的一句话：

```text
工具失败不是一个布尔值，而是一条可追踪、可解释、可恢复的执行链路。
```

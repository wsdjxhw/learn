# 30 分钟抓住本模块核心链路

> 不想从第一行读到最后一行的，从这里开始。读完这一页，你就知道本模块在解决什么、代码从哪进、往哪走。

## 第 0-5 分钟：先跑起来，看它长什么样

```bash
cd examples/agent/15_database_tool_agent
python run_demo.py
```

不用配任何东西，mock 模式直接跑。你会看到：查询直接出数据、写操作先生成确认单、审批后订单才生效、viewer 想删订单被拦。

**现在你心里已经有答案了**：本模块 = 查询直出 + 写入确认 + 权限拦截 + 审计。

## 第 5-15 分钟：读两条核心链路

打开代码，按这个顺序读，不要跳：

```text
1. main.py 的 agent_chat()           —— 接口入口：参数从哪来（body + X-API-Key 请求头）
2. agent.py 的 run_agent()           —— Agent 循环：决定工具 -> 执行 -> 观察 -> 回答
3. tool_registry.py 的 execute_tool()—— 执行中枢：权限 -> 校验 -> 确认门 -> 执行 -> 审计
4. tool_registry.py 的 approve_confirmation() —— 审批：按参数快照真正执行写工具
```

读的时候盯着这四个问题：

- 参数从哪来？（问题在 body，身份在请求头，工具参数由"模型决策 + Pydantic 校验"共同保证）
- 写操作为什么没有直接执行？（`execute_tool` 里第 3 道门：`awaiting_confirmation`）
- 审批后发生了什么？（`approve_confirmation` 用 `require_confirm=False` 再走一遍 `execute_tool`）
- 每一步为什么都有日志？（`audit.log_operation` 在 execute_tool 的每一个出口被调用）

## 第 15-25 分钟：看数据怎么进出的

- `schemas.py` 的 `QueryOrdersArgs / UpdateOrderStatusArgs`：参数模型 = 第一层校验。
- `query_tools.py` 的 `handle_query_orders`：JOIN 出客户姓名；`handle_query_stats`：聚合统计。
- `write_tools.py` 的 `ALLOWED_TRANSITIONS`：订单状态机 = 第二层业务校验。

## 第 25-30 分钟：做一次验证

在 `/docs` 里（先 `uvicorn main:app --reload`）用 operator Key 走一遍：

```text
POST /agent/chat  "给订单2发货"   -> 得到 confirmation_id
GET  /confirmations                -> 看到 pending
POST /confirmations/{id}/approve   -> 订单2 变已发货
GET  /audit-logs                   -> 看到 requested + executed 两条记录
```

完成。你现在知道：**这个 Agent 怎么保证写操作安全、怎么做到可追溯。**

## 学完这 30 分钟，你可以再决定要不要深入

- 想懂"为什么模型生成的 SQL 不能直接执行" → 读 `sql_safety.py` + BASICS 文档第 6 节。
- 想懂"业务校验长什么样" → 做 README 练习二。
- 想证明安全底线可靠 → 跑 `python -m pytest tests/ -v`（10 个用例，全绿）。

深入入口：`DATABASE_AGENT_BASICS.md`（概念）和 `DATABASE_AGENT_EXPLAINED.md`（代码按链路讲解）。

# 数据库工具智能体 · 代码讲解（按核心链路读，不逐行）

这篇文档按**三条核心链路**解释代码结构。读之前先跑一遍 `python run_demo.py`，看到现象再回来对代码，效果最好。

---

## 链路一：查询链路（用户问 → Agent 选工具 → 直接执行 → 回答）

### 入口：`main.py` 的 `agent_chat()`

```python
@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(req: ChatRequest, user: UserContext = Depends(get_current_user)):
    provider = get_provider()
    return run_agent(req.question, user, provider)
```

**参数从哪里来（初学者必看）：**

- `req`：请求体里的 JSON，比如 `{"question": "统计各状态的订单数量"}`。FastAPI 根据类型 `ChatRequest` 自动解析，所以 `req.question` 就是用户说的话。
- `user`：来自 `Depends(get_current_user)`。`security.py` 里 `get_current_user` 的参数 `x_api_key: str = Header(...)` 让 FastAPI 去**请求头**里找 `X-API-Key`，然后映射成角色。**这就是"参数从哪来"：body、header、path、query、dependency，每一种都有固定的取法。**

### 流程：`agent.py` 的 `run_agent()`

```python
for _ in range(settings.max_agent_steps):
    decision = provider.decide_tool(question, user.role, visible_tools, feedback)
    if decision is None:
        break                      # 模型认为不需要工具，直接回答
    result = execute_tool(decision.tool_name, decision.args, user.role, user.api_key)
    ...
answer = provider.compose_answer(question, last_result, user.role)
```

它把"Agent"拆成两个动作，正好对应 `provider.py` 里的两个方法：

| 方法 | 干什么 | mock 实现 | DeepSeek 实现 |
|---|---|---|---|
| `decide_tool` | 要不要调工具、调哪个、参数是什么 | 关键词规则 | OpenAI function calling |
| `compose_answer` | 根据工具结果生成人话回答 | 模板拼接 | 聊天补全 |

**这是本模块设计的核心解耦**：无论底层是 mock 还是 DeepSeek，`run_agent` 的流程代码一字不改。切换模型只改 `settings.MOCK_MODE`。

### 执行：`tool_registry.py` 的 `execute_tool()` —— 一切工具的统一入口

查询链路里它走 4 步：

```python
# 第 1 道门：权限
if not has_role(tool.min_role, role):      # viewer 能用只读工具，operator 以上才能写
    ... 记录 blocked -> return

# 第 2 道门：参数校验
validated = tool.arg_model(**args)          # Pydantic：类型/枚举/范围
...
# 第 3 道门：写操作确认（查询工具 is_write=False，直接跳过）
if tool.is_write and tool.requires_confirmation and require_confirm:
    ... 创建确认单 -> return awaiting_confirmation

# 第 4 步：真正执行 handler
result = tool.handler(validated, role)      # query_tools.py 里生成 SQL 查库
```

**为什么所有工具必须共用这一个入口？** 因为安全规则只有写在一处才不会漏。如果每个工具各自校验，谁能保证所有人都记得加权限检查？统一入口 = "没有漏网之鱼"。

### 数据：`query_tools.py` 的 handler

以 `handle_query_orders` 为例，重点看 JOIN：

```python
stmt = (
    select(Order, Customer.name)                 # 同时取订单和客户名
    .join(Customer, Order.customer_id == Customer.id)  # 用外键把两表连起来
    .order_by(Order.id)
)
```

**为什么 JOIN？** orders 表里只有 `customer_id`（外键），看不到客户叫啥。想展示"张三买了显示器"这种答案，必须把客户表连进来取 `Customer.name`。这就是关系数据库的日常操作。

`handle_query_stats` 用聚合（GROUP BY）：

```python
select(
    Order.status,
    func.count(Order.id).label("order_count"),   # 每堆多少单
    func.sum(Order.amount).label("total_amount"),# 每堆金额合计
).group_by(Order.status)
```

`func.count` / `func.sum` 是 SQL 的聚合函数，把订单按状态"分堆"再计数求和——这就是"统计各状态的订单数量"背后真正的 SQL。

### 回答：`provider.py` 的 mock `compose_answer`

```python
if "rows" in data:   # 查询类
    head = f"查询完成，共 {data['count']} 条记录："
    return head + "\n" + "\n".join(_format_rows(...))
```

mock 直接用工具返回的数据拼句子，把英文状态转中文（`format_status_cn`）。DeepSeek 则把同样的数据塞进提示词，让它组织成人话。

> **读到这里，查询链路就通了。** 请求 → 决策 → 权限/校验 → 生成 SQL → 查库 → 拼回答。

---

## 链路二：写操作确认链路（写请求 → 确认单 → 审批 → 真正执行）

### 第 1 步：写操作被"确认门"拦下

用户问"给订单2发货"，mock 的 `decide_tool` 匹配到"发货"→ 返回 `update_order_status(order_id=2, new_status="shipped")`。

`execute_tool` 走到第 3 道门：

```python
req = confirmation.create_request(tool_name, args, api_key, role)
log_operation(..., status="requested", confirmation_id=req.id)
return ToolResult("awaiting_confirmation", f"写操作已创建确认单 #{req.id} ...", confirmation_id=req.id)
```

**关键点：订单没有被改！** 只是往 `confirmation_requests` 表里插入了一行 pending 记录，存下工具名和参数快照（`args_json`）。Agent 据此回答用户："已发起确认，等待审批"。

### 第 2 步：审批人看到待办

`GET /confirmations` 走 `confirmation.list_requests()`，返回 pending 的确认单。界面（或文档按钮）展示：谁发起的、想执行哪个工具、参数是什么、什么时间。

### 第 3 步：批准 → 真正执行（`approve_confirmation`）

```python
# 校验 1：确认单存在且是 pending
# 校验 2：审批人角色必须满足该工具的 min_role
args = json.loads(req.args_json)                # 用"参数快照"执行
result = execute_tool(req.tool_name, args, role, api_key,
                      require_confirm=False,    # 关键：不再二次确认
                      confirmation_id=confirmation_id)
```

`require_confirm=False` 让 `execute_tool` **跳过第 3 道门**，直接走 handler 真正写库。执行后把确认单标记为 `executed`（或失败时 `failed`）。

**为什么叫"参数快照"？** 如果审批时重新让模型生成参数，用户看到的是"删订单3"，执行的可能变成"删订单9"。快照保证"批的就是你看到的"。

### 第 4 步：拒绝 → 不执行（`reject_confirmation`）

直接把确认单标记为 `rejected`，写审计。数据库**没有任何改动**。

> **写链路总结**：写操作 = 申请（pending）→ 决策（approve/reject）→ 执行/不执行。模型全程没有"直接改库"的能力，这是本模块最重要的安全设计。

---

## 链路三：安全与审计链路

### 三个角色为什么看到不同工具

`main.py` 的 `GET /tools` 调 `visible_tools_for_role(role)`：

```python
[t for t in TOOLS.values() if has_role(t.min_role, role)]
```

viewer 的角色等级是 1，只读工具 `min_role="viewer"` 才满足，所以只看到 3 个工具；operator 等级 2，能看到全部 7 个。**权限不是执行时才拦，而是从"你看得到什么工具"就开始分层。**

### 审计为什么在 execute_tool 的每个出口

`execute_tool` 里每一道门失败都调 `log_operation(...)`：未知工具（failed）、权限不足（blocked）、参数非法（failed）、创建确认单（requested）、执行成功（executed）、业务规则失败（failed）、兜底异常（failed）。加上 approve/reject 的记录，覆盖了 `requested/executed/rejected/blocked/failed` 全部状态。

`audit.py` 用一个**独立的 Session** 写日志，注释里写清了原因：业务失败导致事务回滚时，日志不能跟着回滚，否则这次失败就永远查不到了。

### 只读 SQL 的安全层（`sql_safety.py`，进阶）

```python
# 黑名单：以 DROP/UPDATE/... 开头的一律拦截
BLOCKED_PREFIX = re.compile(r"^\s*(insert|update|delete|drop|alter|create|...)\b", re.I)
# 白名单：必须以 SELECT / WITH 开头
if not re.match(r"^\s*(select|with)\b", sql, re.I): raise ...
# 防多语句：有分号就拦
if ";" in sql: raise ...
# 防危险函数 / 系统表
# 强制 LIMIT：没有就补，太大就重写
```

先 `_strip_comments` 剥掉注释再检查，是"先消毒再检测"的经典手法（防止 `SELECT 1 -- ; DROP TABLE` 藏注释绕过）。执行时 `execute_readonly_sql` 用 `text(sql)` + `result.keys()` 拿列名，`_json_safe` 处理 datetime/Decimal 的序列化问题。

---

## mock 模式是怎么"假装 AI"的

mock 不是真模型，它是**把"哪些问题该调哪个工具"写死成规则**：

```python
# provider.py 的 MockProvider.decide_tool
if any(k in q for k in ["发货", "改状态", "更新状态"]):      # 命中 -> 选写工具
    return ToolDecision("update_order_status", {...})
if any(k in q for k in ["统计", "总额", "汇总", "多少单"]):  # 命中 -> 选统计
    return ToolDecision("query_order_stats", {"group_by": ...})
if "订单" in q: ...                                          # 命中 -> 查订单
```

参数也是用正则粗提取的：`订单\s*#?(\d+)` 抓订单号、`客户\s*#?(\d+)` 抓客户号。

**mock 的局限（刻意保持的）**：它不理解复杂话术、提取参数很笨。这正是教学要的效果——**让你意识到"模型决策"才是 Agent 的灵魂，mock 只是替你跑通流程**。切到 `MOCK_MODE=false`，同样的问题让 DeepSeek 用 function calling 处理，你会看到真正灵活的解析。

---

## 要改需求，改哪里（速查）

| 需求 | 改动 |
|---|---|
| 加查询工具 | `schemas.py` 加参数模型 → `query_tools.py` 加 handler → `tool_registry.py` 注册 → `provider.py` 加 mock 规则 |
| 加写工具 | 同上 + 注册表里标 `is_write=True, requires_confirmation=True` |
| 加业务规则 | `write_tools.py` 里抛 `BusinessRuleError`，`tool_registry` 自动转成 failed 并审计 |
| 改权限 | `tool_registry.py` 的 `min_role`（一行） |
| 加 SQL 防护 | `sql_safety.py` 加黑名单/规则 + `tests/test_safety.py` 加用例 |
| 加新表 | `models.py` + `seed.py` + 对应查询/写工具 |

**你会发现：注册表是"接线板"，schemas 是"接口契约"，handler 是"干活的人"。** 新需求大多只需在这三处做加法，这也是真实项目里给 Agent 扩展能力的日常。

---

## 读完自查：你该能回答

1. 写操作为什么不直接执行？确认单里存了什么？审批时按什么执行？
2. viewer 发起写操作会发生什么？审计里记的是什么状态？
3. 参数校验有三层，各在哪一层？为什么业务规则必须放在 handler 里？
4. `run_sql_readonly` 为什么安全？它怎么防止 DROP 和无 LIMIT 全表扫描？
5. 如果审计只记成功，会漏掉什么？为什么？

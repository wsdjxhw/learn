# 15 数据库工具智能体（Database Tool Agent）

> 让 Agent 用自然语言查询和修改数据库：**查询直接执行，写入必须人工确认，所有操作可审计。**
>
> 前置：已学完 `14_production_rag`。本模块把前面学过的"工具注册表 + 权限 + 确认 + 审计 + mock/DeepSeek 双模式"整体迁移到**结构化业务数据**上。

---

## 1. 本模块解决的真实工程问题

业务人员不会写 SQL，但每天都要问："上个月的订单总额是多少？""北京的客户有谁？""能不能帮我把这张订单发货？"

于是团队想做"数据库智能体"：让用户用自然语言提问，Agent 自己选工具、查数据、给答案。

但把数据库交给大模型，有三层致命风险，这也是本模块要解决的核心问题：

| 风险 | 例子 | 后果 |
|---|---|---|
| **破坏性** | 模型生成 `DROP TABLE orders`、`DELETE FROM orders` | 数据全没，无法恢复 |
| **越权** | 模型生成的 SQL 绕过业务权限，读到不该读的数据 | 信息泄露 |
| **不可追溯** | 出了问题不知道是谁、什么时间、干了什么 | 无法排查、无法追责 |

所以真实项目（以及本模块）的答案是 **"安全三角"**：

```text
查询工具 -> 直接执行（只读，风险低）
写入工具 -> 权限检查 -> 参数校验 -> 人工确认 -> 才真正执行
所有操作 -> 写进审计日志（成功、被拦、被拒、失败都要记）
```

---

## 2. 学完这个模块，你能讲出 / 能做什么

**面试 / 真实开发能讲：**

- 为什么"模型生成的 SQL 不能直接执行"——破坏性、越权、性能三层风险。
- 为什么写操作必须人工确认，以及确认单如何保存"参数快照"、如何流转。
- 参数校验的三层：类型/枚举（Pydantic）→ 存在性（外键/记录是否存在）→ 业务规则（状态机、删除限制）。
- 审计日志为什么要连"失败的尝试"一起记，而不只是成功记录。
- 工具注册表为什么是安全基座：模型只能从白名单里选工具，所有工具共用一个执行入口。

**能动手做：**

- 在 `/docs` 里用三个角色 Key 演示查询、写请求、审批、审计的完整闭环。
- 新增一个查询工具 / 写入工具 / 业务规则 / SQL 防护，并验证它被正确拦截或执行。
- 跑 `tests/test_safety.py`，证明核心安全底线不是靠自觉，而是靠自动化测试。

---

## 3. 本模块 3-5 个核心知识点（重点）

| # | 核心知识点 | 一句话理解 |
|---|---|---|
| 1 | **数据库 Agent 的安全三角** | 权限（谁能用）→ 校验（参数合不合法）→ 确认（写操作要批准），每一道门都写审计日志 |
| 2 | **读/写工具的安全边界** | 查询直接执行；写操作（create/update/delete）必须人工确认后才生效；不同角色看到不同工具 |
| 3 | **参数校验的三层防线** | Pydantic 类型/枚举 → 记录存在性（外键）→ 业务规则（状态机、删除限制），逐层加深 |
| 4 | **LLM 生成的 SQL 不可信** | `run_sql_readonly` 用黑名单 + 白名单 + 强制 LIMIT 兜底，只放行安全只读查询 |
| 5 | **工具注册表 + 执行中枢** | 所有工具定义在一处，执行统一走 `execute_tool()`，才能保证权限/校验/审计没有漏网之鱼 |

> 学完如果只记住一句话，记住这句：**数据库智能体的核心不是"能查"，而是"查得安全、写得受控、出事了查得出来"。**

---

## 4. 真实项目通常怎么做 vs 教学版简化

| 维度 | 真实项目（企业级） | 本教学模块 |
|---|---|---|
| 数据库 | PostgreSQL + 连接池 + 迁移工具（Alembic） | SQLite 文件，零依赖可跑 |
| 权限 | 行级权限（用户只能看自己的数据）、字段级脱敏 | 角色级权限（viewer/operator/admin），无行级隔离 |
| 参数校验 | 同上三层，可能还接规则引擎 | 三层，写在 Python 里，足够教学 |
| 写确认 | 接审批流系统（谁有权限批、审批链、超时） | 任一 operator 以上角色可批，状态 pending/executed/rejected/failed |
| SQL 安全 | 用 SQL AST 解析器 + 语句白名单 + 慢查询拦截 + 单独只读账号 | 正则黑名单 + 强制 LIMIT（够教学，不够生产） |
| 身份 | JWT / OAuth / session | 静态 API Key 映射角色 |
| 模型 | GPT/Claude/DeepSeek + 多轮上下文 + 流式 | DeepSeek（function calling）或 mock 规则 |
| 审计 | 集中式日志 + 审计平台 + 保留策略 | `database_op_logs` 表，可查询 |

**必须理解（企业级）**：安全三角、三层校验、参数快照、审计连失败一起记、LLM-SQL 风险。
**只要让示例跑起来（教学简化）**：mock 的粗糙关键词解析、SQLite、正则式 SQL 校验、静态 Key。

---

## 5. 和前后模块的关系

**复用了前面这些能力：**

- 模块 `10-12`：工具注册表、角色权限、写操作确认单、审计日志模式（本模块独立实现，不拷贝代码）。
- 模块 `13-14`：把能力包装成 Agent 可主动调用的工具 + mock/DeepSeek 双模式。
- 模块 `02`：Agent 循环（思考 → 工具 → 观察 → 回答）。
- 模块 `05`：Pydantic 参数校验思想。
- 阶段 5 / `03_sqlalchemy_database`：SQLAlchemy ORM 建表和查询。

**为后面这些模块做准备：**

- `16_background_task_agent`：本模块的"结构化业务工具 + 确认 + 审计"就是它要复用的地基。
- `18_agent_workspace_ui`：`steps`、确认单、审计日志都是前端工作台要展示的面板。
- `22_agent_safety`：本模块的权限/审计是安全专题的起点。
- `23_agent_testing`：本模块的 `tests/test_safety.py` 是"给 Agent 写测试"的第一次实践。
- 完整项目二 `projects/agent_business_assistant`：本模块几乎就是它的最小原型。

---

## 6. 启动方式

```bash
cd examples/agent/15_database_tool_agent

# 1. 安装依赖（如果还没装）
pip install -r requirements.txt

# 2. 方式 A：命令行 demo（推荐先跑这个，5 秒看懂全链路，不用起服务）
python run_demo.py

# 2. 方式 B：启动 Web 接口
copy .env.example .env      # Windows；Mac/Linux: cp .env.example .env
uvicorn main:app --reload
# 浏览器打开 http://127.0.0.1:8000/docs
```

默认是 **mock 模式**，不需要任何 API Key。想切真实模型：改 `.env` 里 `MOCK_MODE=false` 并填 `DEEPSEEK_API_KEY`。

---

## 7. 接口测试顺序（按这个顺序在 /docs 里点）

先在请求头填 `X-API-Key`。三个角色的 Key 在 `.env.example` 里，默认值：

| 角色 | API Key | 能力 |
|---|---|---|
| viewer | `sk-viewer-0000000001` | 只能查询 |
| operator | `sk-operator-0000000001` | 查询 + 发起写操作 + 审批 |
| admin | `sk-admin-0000000001` | 同 operator（本模块保留确认环节） |

| 步骤 | 接口 | 用什么 Key | 看什么 |
|---|---|---|---|
| 1 | `GET /` | 任意 | 接口清单 |
| 2 | `GET /tools` | viewer | 只看到 3 个只读工具 |
| 3 | `POST /agent/chat` | viewer | 问题："统计各状态的订单数量" → 返回统计数据 + steps |
| 4 | `GET /tools` | operator | 看到全部 7 个工具（含写工具） |
| 5 | `POST /agent/chat` | operator | 问题："给订单2发货" → 返回 **confirmation_id**，订单没变 |
| 6 | `GET /confirmations` | operator | 看到 pending 确认单（含参数快照） |
| 7 | `POST /confirmations/{id}/approve` | operator | 审批后订单2 才真正变成已发货 |
| 8 | `GET /audit-logs` | operator | 看到 requested → executed 的完整轨迹 |
| 9 | `POST /tool/run` | operator | 手动试 `query_orders`，args `{"status":"pending"}` |
| 10 | `POST /agent/chat` | viewer | 问题："删除订单8" → 被拦（blocked），但审计里有记录 |
| 11 | `GET /confirmations` | viewer | 403（viewer 无权看审批队列） |
| 12 | `POST /tool/run` | operator | 进阶：`run_sql_readonly` 传 `SELECT * FROM orders`，再试 `DROP TABLE orders`（被拦） |

> 想一条命令直接验证？先跑 `python run_demo.py`，它把 1-10 的核心链路自动演示一遍。

---

## 8. 代码阅读路线

### 如果只有 30 分钟，只看这条链路

```text
main.py 的 /agent/chat
   -> agent.py 的 run_agent（Agent 循环）
   -> tool_registry.py 的 execute_tool（执行中枢：权限->校验->确认->审计）
   -> query_tools.py / write_tools.py 的 handler（真正操作数据库）
   -> schemas.py 的参数模型（为什么参数在这里被校验）
```

30 分钟内：跑一遍 `python run_demo.py`，然后**精读 agent.py 全文 + tool_registry.py 的 execute_tool**，再扫一眼 query_tools / write_tools 的 handler。够你回答"这个 Agent 怎么保证写操作安全"。

### 必须精读

| 文件 | 读哪里 |
|---|---|
| `agent.py` | 全文（Agent 循环，最短的核心链路） |
| `tool_registry.py` | `execute_tool()`、`approve_confirmation()`（安全三角的落地） |
| `write_tools.py` | `ALLOWED_TRANSITIONS` 状态机、`UNSAFE_TO_DELETE` 删除规则（业务规则校验） |
| `schemas.py` | 各 `Args` 参数模型（Pydantic 校验 = 第一层防线） |
| `query_tools.py` | `handle_query_orders` 的 JOIN、`handle_query_stats` 的聚合 |

### 可以粗读

| 文件 | 为什么粗读 |
|---|---|
| `provider.py` | mock 的关键词规则只是"教学假模型"，重点看 `decide_tool` 和 DeepSeek 的 function calling 入口即可 |
| `main.py` | 其它接口（tools/confirmations/audit-logs）套路一致，读 `agent_chat` 一个就够 |
| `security.py` / `audit.py` / `confirmation.py` | 职责单一，扫一眼结构就懂 |
| `settings.py` / `database.py` / `seed.py` | 配置、连接、种子数据，之前模块都见过 |

### 暂时不用管

- `sql_safety.py` 的正则细节（**进阶**：先知道"它拦住了什么"即可，面试时能讲思路）——本模块 30 分钟链路可以跳过它。
- `tests/`（等你做练习三时再回来改它）。
- `main.py` 里 `list_tools` / `list_audit_logs` 的过滤参数实现。

### 如果要改一个需求，改哪些文件

| 需求 | 改哪些文件 |
|---|---|
| 加一张新业务表 | `models.py` + `seed.py` + `query_tools.py` 加查询 |
| 加一个查询工具 | `schemas.py`（参数模型）→ `query_tools.py`（handler）→ `tool_registry.py`（注册）→ `provider.py`（mock 规则，可选） |
| 加一条业务规则 | `write_tools.py`（抛 `BusinessRuleError`） |
| 加一个写工具 | 同查询工具 + 在注册表标 `is_write=True, requires_confirmation=True` |
| 改工具权限 | `tool_registry.py` 的 `min_role` |
| 加一个 SQL 防护 | `sql_safety.py` + 在 `tests/test_safety.py` 加用例 |

---

## 9. 练习任务（对应真实工程能力）

> 每个练习都能在 `/docs` 或测试里**看到可验证的结果**，不是改数字、改文案。

### 练习一：给 Agent 新增一个查询工具（对应真实能力：新报表需求）

业务方想看"谁买得最多"。请新增工具 `query_top_customers`（按订单总金额降序返回客户排行）。

要求：
1. 在 `schemas.py` 加参数模型 `QueryTopCustomersArgs`（比如 `top_n: int = Field(default=5, gt=0)`）。
2. 在 `query_tools.py` 写 handler：JOIN customers + orders，`group_by(customer_id)` + `sum(amount)` 降序，取前 top_n。
3. 在 `tool_registry.py` 注册，`min_role="viewer"`，写好 description（模型靠它选工具）。
4. 在 `provider.py` mock 规则里加一行：问题含"排行/谁买得多/最多"时选它。
5. 验证：`GET /tools`（viewer）能看到它；`POST /tool/run` 手动跑它；`POST /agent/chat` 问"客户消费排行"能看到真实数据。
6. 加分：去 `/audit-logs` 确认这次查询的 SQL 被记录。

### 练习二：加一条业务规则（对应真实能力：风控 / 业务校验）

现状：`create_order` 只校验了客户存在。请新增规则：**同一个客户累计"未付款（pending）"的订单不能超过 3 条**，超过时抛 `BusinessRuleError` 并给出清晰提示。

要求：
1. 在 `write_tools.py` 的 `handle_create_order` 里，先 `select(func.count())` 统计该客户 pending 订单数。
2. 超过 3 条就 `raise BusinessRuleError(...)`。
3. 验证：用 seed 数据（客户4 有 1 条 pending）连续给客户4 发起多次创建订单并审批，到第 4 条时审批失败、审计里能看到 failed 及原因。

### 练习三：给只读 SQL 加一条防护 + 补测试（对应真实能力：安全加固 + 测试）

现状：`sql_safety.py` 已能拦 DROP / 多语句 / 系统表。请再加一条防护：

1. 禁止 `SELECT *`（要求查询必须列出字段）。提示：正则匹配 `select\s+\*\s+from`（注意大小写与换行）。
2. 在 `tests/test_safety.py` 加两个用例：`SELECT * FROM orders` 应抛 `SqlSafetyError`；`SELECT id FROM orders` 应放行。
3. 跑 `python -m pytest tests/ -v`，确认全部通过。
4. 思考题（写进你的笔记）：为什么"禁止 SELECT *"对生产环境有意义？提示：字段多了数据可能不该被看到、扫描变慢。

### 练习四：三角色权限走查（对应真实能力：验收测试 / 交付前的安全自检）

用 viewer / operator / admin 三个 Key，在 `/docs` 里走一遍，并记录：

| 场景 | viewer 预期 | operator 预期 |
|---|---|---|
| 查询订单 | 成功 | 成功 |
| 发起"删除订单" | blocked | 生成确认单 |
| 查看确认单队列 | 403 | 成功 |
| 批准确认单 | 403 | 成功 |
| 查看审计日志 | 403 | 成功 |

最后做一个小设计判断（写出你的答案）：**admin 应该跳过人工确认直接执行写操作吗？** 提示：真实项目里"越大的权限越要留痕"，本模块为什么让 admin 也走确认？

---

## 10. 常见坑（提前给你打好预防针）

- **时间对象 JSON 报错**：数据库返回的 `datetime` 不能直接 `json.dumps`，本模块用 `strftime` 和 `_json_safe()` 处理，看到这类报错别慌。
- **事务里删了对象再访问字段**：`db.delete(order)` 后对象已失效，先保存 id 再删（`write_tools.py` 里有示范）。
- **参数校验 ≠ 业务规则**：`schemas.py` 管"类型对不对"，`write_tools.py` 管"业务上允不允许"，别混在一起写。
- **mock 很笨是正常的**：mock 用关键词猜参数（比如"客户2"才提取到），它只是教学假模型；真实解析交给 DeepSeek，别在 mock 上较真。

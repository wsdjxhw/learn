# 数据库工具智能体 · 基础知识扫盲

这份文档把"数据库智能体"相关的概念一次讲透：它是什么、真实项目怎么做、为什么必须安全、本模块怎么教的、以及面试怎么讲。

---

## 1. 什么是数据库智能体（Text-to-SQL 的另一种形态）

一句话：**用户用自然语言提问题，Agent 把问题翻译成数据库操作，做完再翻译回人话。**

常见的两种产品形态：

| 形态 | 例子 | 本质 |
|---|---|---|
| **Text-to-SQL** | "上个月北京地区卖了多少？" → 生成 `SELECT ...` → 执行 → 返回 | 模型直接生成 SQL 去执行 |
| **业务工具型（本模块）** | "北京的客户有谁？" → 选 `query_customers(city="北京")` → 后端生成安全的 SQL | 模型选工具，SQL 由后端白名单代码生成 |

**为什么本模块用"业务工具型"而不是"模型直接写 SQL 自由执行"？**

因为自由 SQL 的执行风险太高（见第 3 节）。真实企业里的"业务 Copilot"（比如 CRM/ERP 里的智能助手）绝大多数走的是业务工具型：把"查客户""改订单状态"封装成工具，模型只能在工具清单里选。**模型不写 SQL，SQL 永远是后端受控代码写的。**

> 但"模型直接写只读 SQL"也确实是一种真实能力（给分析师用的"SQL 查询"功能），所以本模块保留了 `run_sql_readonly` 作为进阶工具——但给它套了严格的安全校验（第 6 节）。

---

## 2. 一条完整的查询链路长什么样

```text
用户: "统计各状态的订单数量"
  │
  ▼
模型 decide_tool: 这是一个统计需求 -> 选 query_order_stats, group_by="status"
  │
  ▼
execute_tool:
  ① 权限检查   viewer 能用吗？ 能（只读工具，viewer 可用）
  ② 参数校验   group_by="status" 合法吗？ 合法（枚举之一）
  ③ 确认门     是写操作吗？ 不是 -> 跳过
  ④ 执行       handler 生成 SQL: SELECT status, count(id), sum(amount) FROM orders GROUP BY status
  ⑤ 审计       status=executed, 记下 SQL 和行数
  │
  ▼
Agent 把结果转成 observation 给模型
  │
  ▼
模型 compose_answer: "共 5 种状态，其中已发货 2 单、共 5598 元……"
```

注意第 ④ 步：**SQL 是后端代码生成的**（`query_tools.py` 里写死的 `select(...)`），不是模型生成的。这就是安全性的来源之一。

---

## 3. 为什么"模型生成的 SQL 不能直接执行"（面试必讲）

这是数据库智能体最重要的安全问题，一定要能讲清三层风险：

### 风险 1：破坏性（DML/DDL）

模型完全可能（或被 prompt 注入诱导）生成：

```sql
DROP TABLE orders;
DELETE FROM orders;
UPDATE orders SET amount = 0;
```

一次执行，数据就没或坏了。

### 风险 2：越权 / 信息泄露

用户只该看自己的数据，但 SQL 没有业务权限概念：

```sql
SELECT * FROM orders WHERE customer_id != '我';   -- 读别人订单
SELECT name FROM sqlite_master;                    -- 读出表结构
```

### 风险 3：性能 / 资源耗尽

```sql
SELECT * FROM orders;      -- 没 LIMIT，百万行全查出来，把数据库打垮
```

**应对思路（本模块的答案）：**

1. **不自由**：默认用业务工具，SQL 由受控代码生成 → 破坏性风险直接消失。
2. **只读 SQL 也要验**：`run_sql_readonly` 用黑名单拦关键字、白名单限 SELECT/WITH、强制 LIMIT → 越权和性能风险被压住。
3. **写操作人工确认**：模型永远不能直接改库，改库前必须有人点头。
4. **权限 + 审计兜底**：谁在什么时候想干什么，全部留痕。

> 面试如果被问"你的数据库 Agent 怎么防 SQL 注入/DROP？"，把这条"四层防护"按顺序讲出来，就赢了。

---

## 4. 读/写工具的安全边界

**这是本模块最重要的设计思想：读和写不是一回事。**

| | 查询工具 | 写入工具 |
|---|---|---|
| 工具 | query_customers / query_orders / query_order_stats / run_sql_readonly | create_order / update_order_status / delete_order |
| 风险 | 低 | 高（会改数据库） |
| 权限 | viewer 起 | operator 起 |
| 人工确认 | 不需要，直接执行 | **必须确认**，确认前绝不执行 |
| 审计 | 记 SQL 和行数 | 记 requested / executed / rejected / failed 全流程 |

代码里的体现：

```python
# tool_registry.py 注册表里，每个工具都有这四个字段
ToolMeta(
    min_role="operator",        # 谁能用
    is_write=True,              # 是不是写操作
    requires_confirmation=True, # 要不要确认
    risk="high",                # 风险等级
)
```

**模型永远接触不到"没有登记的工具"**，这就是白名单的意义。

---

## 5. 写操作人工确认（Confirmation）

真实世界里"删除一条订单"这种操作，不会是模型自己说了算的。流程是这样的：

```text
Agent 想执行 delete_order(order_id=3)
  -> 创建确认单 ConfirmationRequest(status=pending, 参数快照{"order_id":3})
  -> 订单本身没被删
  -> 审批人在 /confirmations 看到这条待办
  -> 批准：按"参数快照"执行真正的 delete -> 状态 executed
  -> 拒绝：不执行 -> 状态 rejected
```

**两个容易被忽略的设计点：**

1. **参数快照（args_json）**：确认单里保存的是"发起那一刻的参数"。审批时严格按这份参数执行，而不是审批时重新生成。避免"发起时说删订单3，审批时却变成删订单5"。
2. **审批人也要过权限**：`approve_confirmation` 里会再检查一次审批人的角色够不够。低权限者不能批高权限操作。

**状态流转**：`pending → executed / rejected / failed`。failed 是"批准了但执行时失败"（比如业务规则拦截）。

> 思考：为什么不是"写工具直接执行 + 事后审计"？因为很多破坏是**不可逆**的。确认机制是把"不可逆操作"变成"可撤销决策"。

---

## 6. run_sql_readonly 的只读 SQL 安全校验（进阶但必懂）

`run_sql_readonly` 允许提交一段 SQL 查询。它用三层防护（`sql_safety.py`）：

| 层 | 做法 | 拦住什么 |
|---|---|---|
| 语句形态 | 必须 `SELECT`/`WITH` 开头，且不能有分号 | 多条语句、破坏性语句 |
| 黑名单 | `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE...`、`load_extension` 等危险函数、`sqlite_master` 等系统表 | 写操作、文件读写、结构泄露 |
| 白名单兜底 | 自动补 `LIMIT`，超上限重写 | 无 LIMIT 全表扫描 |

先剥注释再检查（防止 `SELECT 1 -- ; DROP TABLE` 藏注释里），这是安全校验里常见的"先消毒再检查"思路。

**真实生产里会更强**：用 SQL AST 解析器（如 `sqlglot`）做语句级白名单、用独立只读账号连库（数据库权限层面就杜绝写操作）、加慢查询超时、查询走单独从库。

---

## 7. 参数校验的三层防线

这是本模块"参数校验"要求的完整答案。三层，逐层加深：

```text
第 1 层：类型/枚举/范围校验（schemas.py 的 Pydantic）
    "status" 必须是五个状态之一、order_id 必须 > 0、amount 必须 > 0
    这一层在工具执行前自动完成，脏数据到不了 handler

第 2 层：存在性校验（write_tools.py 的 handler）
    创建订单时客户必须存在（db.get(Customer) 是 None 就报错）
    改状态时订单必须存在

第 3 层：业务规则校验（write_tools.py 的 handler，抛 BusinessRuleError）
    订单状态机：pending 只能 -> paid/cancelled，不能跳
    删除限制：已付款/已发货/已完成的订单不能删
```

第 3 层为什么不能写成 Pydantic？因为"订单3现在是 shipped 所以不能改成 shipped"这种判断，依赖**数据库里的当前状态**，Pydantic 只看到传入参数，看不到库。所以业务规则必须放在能查库的 handler 里。

> 面试高频：Pydantic 校验和业务校验的区别？答：一个验"形"（类型、枚举、范围），一个验"义"（这笔交易合不合业务逻辑），后者依赖数据上下文，必须放在业务层。

---

## 8. 审计日志：为什么"失败的尝试"也要记

本模块的 `database_op_logs` 表记录 `requested / executed / rejected / blocked / failed` 五种状态。

**为什么连被拦下的、失败的都要记？**

审计要回答的不是"谁成功了"，而是：

```text
谁、在什么时间、想对数据库做什么、结果怎样
```

- viewer 想删订单 → blocked → **要记**（这是一次越权尝试，安全事件）
- 模型传了非法参数 → failed → **要记**（可能是模型 bug，需要排查）
- 确认单被拒绝 → rejected → **要记**（业务决策留痕）

如果只记成功，你就永远不知道有多少人在试图越权、有多少模型在犯错。

**日志为什么独立开事务？** 见 `audit.py` 里的注释：业务失败导致事务回滚时，日志不能跟着回滚，否则这次失败就查不到了。日志必须"无论如何都落库"。

---

## 9. 角色权限（viewer / operator / admin）

| 角色 | 查询 | 发起写操作 | 审批写操作 | 看确认单/审计 |
|---|---|---|---|---|
| viewer（只读） | ✅ | ❌（blocked） | ❌ | ❌（403） |
| operator（操作员） | ✅ | ✅（需确认） | ✅ | ✅ |
| admin（管理员） | ✅ | ✅（需确认） | ✅ | ✅ |

本模块刻意让 **admin 也走确认**。真实项目里越是大权限越要留痕——admin 删数据同样要有人为决策过程可追溯。这是一道送分的设计判断题（README 练习四有）。

教学版用三个写死的 API Key 映射角色；真实项目是用户表 + JWT/OAuth 登录。

---

## 10. 订单状态机（业务规则的具体例子）

订单状态为什么不能随便改？因为业务上状态是有顺序的：

```text
pending(待付款) ──> paid(已付款) ──> shipped(已发货) ──> completed(已完成)
      │                  │
      └──> cancelled(已取消) ──┘
```

- 待付款只能去"已付款"或"已取消"
- 已付款只能去"已发货"或"已取消"
- 已发货只能去"已完成"
- 已完成/已取消是终点

代码里用一张表表达：

```python
ALLOWED_TRANSITIONS = {
    "pending":   ["paid", "cancelled"],
    "paid":      ["shipped", "cancelled"],
    "shipped":   ["completed"],
    "completed": [],
    "cancelled": [],
}
```

这就是"状态机"。真实项目里复杂的业务流程（审批流、物流、支付）都是状态机的组合。

---

## 11. 本模块的文件分工（分层再讲一遍）

| 文件 | 层 | 职责 |
|---|---|---|
| `main.py` | HTTP 层 | 接口出入参、依赖注入（X-API-Key、数据库会话） |
| `agent.py` | 流程层 | Agent 循环：决策 → 执行 → 观察 → 回答 |
| `tool_registry.py` | 执行层 | 工具白名单 + 统一执行入口 + 确认/审批 |
| `query_tools.py` / `write_tools.py` | 数据层 | 真正生成 SQL、操作数据库 |
| `sql_safety.py` | 安全层 | 只读 SQL 校验 |
| `schemas.py` | DTO 层 | 接口出入参 + 工具参数模型 |
| `models.py` | ORM 层 | 数据库表结构 |
| `security.py` | 鉴权层 | API Key → 角色、权限比较 |
| `audit.py` | 审计层 | 写审计日志 |
| `confirmation.py` | 数据层 | 确认单的增删改查 |
| `provider.py` | 模型层 | mock / DeepSeek 双模式 |
| `seed.py` / `database.py` / `settings.py` | 基建 | 数据初始化 / 连接 / 配置 |

**为什么拆这么多层？** 因为每一层解决一个问题，改一个需求时只动对应文件（README 第 8 节有"改需求改哪个文件"对照表）。这是企业工程的基本功。

---

## 12. 和前后模块的关系（别把它们看成孤岛）

**前面教会你的，本模块在用：**

- `10-12` 的工具注册表 / 权限 / 确认 / 审计：本模块是这些模式的**业务化落地**（从"演示工具"变成"真实业务工具"）。
- `13-14` 的"把能力包成 Agent 工具 + mock/DeepSeek 双模式"：本模块完全复用这套骨架。
- `02` 的 Agent 循环、`05` 的参数校验、阶段 5 的 SQLAlchemy：都是本模块的零件。

**本模块为后面铺路：**

- `16_background_task_agent`：长任务也要做成"工具 + 状态 + 审计"，本模块是模板。
- `18_agent_workspace_ui`：steps / 确认单 / 审计日志正好是工作台的三块面板。
- `22_agent_safety` / `23_agent_testing`：权限与审计是安全专题起点，`tests/test_safety.py` 是测试专题的第一次实践。
- 完整项目二（业务操作 Agent）：本模块就是它的最小原型。

---

## 13. 面试怎么讲（30 秒版）

> "我做过一个数据库工具智能体。核心不是'能查数据'，而是'安全地操作数据'。我把它拆成三个能力：第一，所有数据库操作都封装成白名单工具，查询工具直接执行，写工具必须人工确认，模型永远碰不到裸 SQL；第二，参数三层校验——Pydantic 类型校验、记录存在性校验、业务规则校验（订单状态机、删除限制）；第三，所有尝试——包括被拦的和失败的——都进审计日志，可以回答'谁在什么时候想对库做什么'。另外我还做了只读 SQL 工具，对模型生成的 SQL 做黑名单 + 白名单 + 强制 LIMIT 的校验。"

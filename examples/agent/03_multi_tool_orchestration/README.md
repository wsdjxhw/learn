# 多工具编排 Multi Tool Orchestration

这个模块是 Agent 进阶路线的第四步。

你已经学过“最小 Agent 循环”后，本模块开始学习一个更真实的问题：一个用户目标通常不是调用一个工具就能完成，而是要拆成多个工具动作，并把前一个工具的输出传给后一个工具。

本模块不调用真实外部模型，使用教学版 planner 模拟“生成执行计划”。这样可以先把多工具编排学清楚：顺序、依赖、数据传递、耗时记录、错误处理和最终回答。

## 学习目标

- 理解一个用户目标如何拆成多个工具动作。
- 理解工具之间的数据如何传递。
- 理解哪些工具可以并行，哪些工具必须串行。
- 理解为什么每一步都要记录输入、输出、耗时和错误。
- 理解一个工具失败后，后续依赖步骤为什么要跳过。
- 能通过 `steps` 排查“最终回答为什么错了或为什么没生成”。

## 文件结构

```text
examples/agent/03_multi_tool_orchestration
├── main.py
├── planner.py
├── orchestrator.py
├── tools.py
├── MULTI_TOOL_ORCHESTRATION_BASICS.md
├── MULTI_TOOL_ORCHESTRATION_EXPLAINED.md
├── README.md
└── requirements.txt
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `planner.py`：教学版计划生成器，模拟模型把目标拆成步骤。
- `orchestrator.py`：编排执行层，负责依赖检查、参数解析、工具执行和 steps 记录。
- `tools.py`：工具定义、工具白名单和具体工具函数。
- `MULTI_TOOL_ORCHESTRATION_BASICS.md`：基础概念扫盲。
- `MULTI_TOOL_ORCHESTRATION_EXPLAINED.md`：逐段解释代码结构。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\03_multi_tool_orchestration
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口页面：

```text
http://127.0.0.1:8000/docs
```

## 接口测试顺序

### 1. 查看健康状态

先测试：

```text
GET /health
```

重点看：

- `planner` 是 `teaching_mock_planner`，表示本模块不用真实模型。
- `tool_count` 表示当前有多少个工具。

### 2. 查看工具清单

再测试：

```text
GET /tools
```

先知道 Agent 能调用哪些工具，再看后面的 plan 和 steps 会更容易理解。

### 3. 预览工具计划

测试：

```text
POST /agent/plan
```

请求体：

```json
{
  "goal": "帮客户判断退款金额，并生成一段客服回复",
  "customer_name": "小王",
  "order_amount": 240,
  "days_since_purchase": 5,
  "item_problem": "破损",
  "policy_keyword": "退款",
  "stop_on_error": false
}
```

重点观察：

- `policy` 和 `risk` 都没有依赖，理论上可以并行。
- `refund` 依赖 `policy` 和 `risk`，必须等它们完成。
- `reply` 依赖 `refund` 和 `policy`，必须最后执行。
- `from_step` 表示某个参数来自前面步骤的输出。

### 4. 执行完整编排

测试：

```text
POST /agent/run
```

使用和上面相同的请求体。

你应该看到：

```text
search_refund_policy
-> evaluate_order_risk
-> calculate_refund
-> draft_customer_reply
```

重点看 `steps` 里的这些字段：

- `arguments`：工具实际收到的输入。
- `output`：工具执行后的结构化输出。
- `duration_ms`：工具耗时。
- `depends_on`：当前步骤依赖哪些前置步骤。
- `planned_reason`：为什么 planner 安排这个步骤。

### 5. 测试工具失败导致流程变化

把 `policy_keyword` 改成一个不存在的关键词：

```json
{
  "goal": "帮客户判断退款金额，并生成一段客服回复",
  "customer_name": "小王",
  "order_amount": 240,
  "days_since_purchase": 5,
  "item_problem": "破损",
  "policy_keyword": "礼品卡",
  "stop_on_error": false
}
```

你应该看到：

- `policy` 步骤失败。
- `risk` 仍然可以执行，因为它不依赖 `policy`。
- `refund` 被跳过，因为它依赖 `policy`。
- `reply` 被跳过，因为它依赖 `refund`。
- 最终 `status` 是 `failed`，但接口本身不会崩溃。

再把 `stop_on_error` 改成 `true`，观察失败后是否立刻停止。

## 练习任务

### 练习 1：增加一个独立准备工具

新增一个 `check_vip_customer` 工具：

- 输入 `customer_name`。
- 输出客户是否 VIP。
- 让它和 `policy`、`risk` 一样属于 `prepare` 阶段。
- 在 `calculate_refund` 里给 VIP 客户增加 5% 退款补偿。

学习价值：练习判断一个工具是否依赖其他工具，以及如何把新工具输出传给后续步骤。

### 练习 2：排查错误数据流

故意把 `planner.py` 里 `refund` 步骤的：

```python
"policy": {"from_step": "policy", "field": "policy"}
```

改成一个不存在的字段，例如：

```python
"policy": {"from_step": "policy", "field": "missing_policy"}
```

重新请求 `/agent/run`，观察 `参数引用失败` 出现在第几步。

学习价值：多工具 Agent 的很多问题不是工具本身坏了，而是前后步骤的数据契约断了。

### 练习 3：设计一个失败后可降级的流程

当前 `policy` 失败后，`refund` 会被跳过。

你可以尝试增加一个 `fallback_policy` 步骤：

- 当制度检索失败时，使用默认人工审核策略。
- 后续 `reply` 不承诺退款金额，只建议进入人工审核。

学习价值：真实 Agent 不应该遇到工具失败就只返回“失败”，而应该尽量给用户一个可执行的下一步。

## 本模块暂时不做什么

- 不调用真实 DeepSeek。
- 不做真正并行执行。
- 不接数据库。
- 不接真实订单系统。

这些能力后续会分别在提示词工程、短期状态管理、工具权限、数据库智能体和生产部署模块里继续补齐。

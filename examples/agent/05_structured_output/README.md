# 结构化输出 Structured Output

这个模块是 Agent 进阶路线的第六步。

你已经学过提示词工程后，本模块开始学习：不要让后端直接相信模型自然语言，而要让模型输出符合固定 JSON 契约，并用代码解析、校验、重试和降级。

本模块默认使用 mock 模式，不需要任何 API Key。mock 模型会稳定生成几类常见坏输出，方便你观察“看起来像 JSON”和“真的能被程序稳定使用”之间的区别。配置 `MODEL_MODE=deepseek` 后，也可以接真实模型。

## 如果第一遍学得发懵

先读：

[START_HERE.md](START_HERE.md)

第一遍不要急着理解所有文件。先抓住这一条主线：

```text
模型原始文本
-> JSON 解析
-> Pydantic 契约校验
-> 失败时重试一次
-> 仍失败时降级为人工审核
```

跑通 `valid_json`、`missing_field`、`broken_json + allow_retry=false` 这三个场景后，再回来看完整 README。

## 学习目标

- 理解为什么生产项目不能只依赖自然语言回答。
- 理解 JSON、JSON Schema、Pydantic Model 的区别。
- 学会用 Pydantic 定义模型输出契约。
- 学会区分 JSON 解析失败和字段校验失败。
- 学会处理缺字段、字段类型错误、非法枚举值。
- 学会在输出不合法时重试一次。
- 学会重试仍失败时返回稳定的降级结构。

## 文件结构

```text
examples/agent/05_structured_output
├── main.py
├── settings.py
├── schemas.py
├── provider.py
├── parser.py
├── agent.py
├── START_HERE.md
├── STRUCTURED_OUTPUT_BASICS.md
├── STRUCTURED_OUTPUT_EXPLAINED.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `settings.py`：读取 `.env` 配置，决定使用 mock 还是真实模型。
- `schemas.py`：请求 DTO 和模型输出契约。
- `provider.py`：模型调用层，默认 mock，也支持 DeepSeek。
- `parser.py`：负责 JSON 解析和 Pydantic 校验。
- `agent.py`：串起模型输出、解析、校验、重试和降级。
- `START_HERE.md`：第一遍学习入口，用更少概念讲清主线。

## 推荐学习顺序

第一遍：

```text
START_HERE.md
-> 启动服务
-> 只测试 valid_json / missing_field / broken_json
-> 看 schemas.py 里的 RefundDecision
```

第二遍：

```text
parser.py
-> agent.py
-> STRUCTURED_OUTPUT_EXPLAINED.md
```

第三遍：

```text
provider.py
-> 真实模型模式
-> 练习任务
```

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\05_structured_output
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置模板：

```powershell
Copy-Item .env.example .env
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

- `model_mode`：默认是 `mock`。
- `schema_name`：当前输出契约是 `RefundDecision`。
- `has_deepseek_api_key`：是否读取到真实模型密钥。

### 2. 查看输出契约

测试：

```text
GET /output-schema
```

重点观察：

- 哪些字段是必填。
- 哪些字段有枚举限制。
- `confidence` 为什么限制在 `0` 到 `1`。
- `additionalProperties: false` 表示不允许多余字段。

### 3. 测试合法 JSON

测试：

```text
POST /agent/run
```

请求体：

```json
{
  "message": "客户说商品破损，订单 240 元，购买 5 天，帮我判断退款金额。",
  "order_amount": 240,
  "days_since_purchase": 5,
  "item_problem": "破损",
  "mock_scenario": "valid_json",
  "allow_retry": true
}
```

你应该看到：

- `status` 是 `succeeded`。
- `retry_used` 是 `false`。
- `decision` 是稳定 JSON 结构。
- `attempts[0].ok` 是 `true`。

### 4. 测试 JSON 外面夹自然语言

把 `mock_scenario` 改成：

```json
"json_with_extra_text"
```

你应该看到仍然成功。原因是 `parser.py` 会尝试从文本中提取第一个 JSON object。

注意：这只是兼容策略，不是推荐模型这样输出。真实项目应该要求模型只返回 JSON。

### 5. 测试缺字段并自动重试

把 `mock_scenario` 改成：

```json
"missing_field"
```

你应该看到：

- 第一次失败在 `pydantic_validation`。
- 错误里会指出 `confidence` 缺失。
- 第二次重试成功。
- `status` 是 `recovered`。

### 6. 测试非法枚举值

把 `mock_scenario` 改成：

```json
"invalid_enum"
```

你会看到第一次输出 `priority: urgent` 被拒绝，因为契约只允许：

```text
low / medium / high
```

这就是枚举字段的价值：后端不会让模型临时发明一个业务系统不认识的值。

### 7. 关闭重试观察降级

请求体：

```json
{
  "mock_scenario": "broken_json",
  "allow_retry": false
}
```

你应该看到：

- `status` 是 `degraded`。
- `decision.decision_type` 是 `manual_review`。
- 即使模型输出坏了，接口仍然返回符合 `RefundDecision` 的结构。

### 8. 批量对比坏输出

测试：

```text
POST /agent/compare
```

这个接口会一次跑多个 `mock_scenario`，适合观察解析失败、校验失败、重试恢复和降级路径。

## 真实模型模式

`.env` 可以改成：

```text
MODEL_MODE=deepseek
DEEPSEEK_API_KEY=你的真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

然后重启服务。

真实模型模式仍然必须经过 `parser.py` 和 Pydantic 校验。不要因为模型支持 JSON 模式就跳过后端校验。

## 练习任务

### 练习 1：新增一个必填字段

在 `RefundDecision` 里新增：

```text
customer_sentiment
```

要求只能是：

```text
angry / neutral / polite
```

然后修改 mock 输出，让合法场景能通过，让非法场景能失败。

学习价值：练习输出契约变更、mock 数据同步、接口验证。

### 练习 2：为 action 参数做二次校验

当前 `ToolAction.arguments` 还是通用 `dict`。请你为 `calculate_refund` 设计一个更严格的参数模型：

- `order_amount` 必须大于等于 0。
- `days_since_purchase` 必须大于等于 0。
- `item_problem` 不能为空。

学习价值：理解“外层模型输出合法”不代表“工具参数一定合法”。

### 练习 3：记录失败原因给前端

现在 `attempts` 已经返回失败阶段和错误。请你设计一个更适合前端展示的字段：

```text
user_debug_message
```

要求它不能直接暴露密钥、完整 prompt 或外部服务响应体。

学习价值：练习错误信息分层：开发者要能排错，用户不能看到内部敏感信息。

## 本模块暂时不做什么

- 不做复杂 Agent 循环。
- 不做上下文裁剪。
- 不做数据库保存。
- 不做自动评测。
- 不做工具权限系统。

这些会在后面的上下文工程、短期状态、运行基座、评测和工具权限模块继续学习。

# 结构化输出代码讲解

## 1. 请求从哪里进入

入口在 `main.py`：

```text
POST /agent/run
```

用户在 `/docs` 里提交 JSON 请求体，FastAPI 会把它转换成 `StructuredRunRequest`。

`StructuredRunRequest` 定义在 `schemas.py`。它校验的是“用户传进来的参数”，不是模型输出。

执行流程是：

```text
HTTP 请求
-> StructuredRunRequest 校验请求体
-> payload.model_dump() 转成 dict
-> run_structured_agent(case)
-> 返回 request 和 result
```

这里的 `payload.model_dump()` 是 Pydantic v2 的方法，用来把模型对象转换成普通 Python 字典。

## 2. 输出契约在哪里

输出契约是 `schemas.py` 里的 `RefundDecision`。

它规定模型最终必须给后端这些字段：

- `decision_type`
- `category`
- `priority`
- `summary`
- `missing_fields`
- `risk_flags`
- `confidence`
- `action`
- `user_visible_answer`

这些字段不是为了好看，而是让后端、前端、测试和后续 Agent 步骤都能稳定消费同一种结构。

`Literal` 用来限制枚举值。比如：

```text
priority 只能是 low / medium / high
```

如果模型输出 `urgent`，Pydantic 会拒绝。

## 3. 模型输出从哪里来

模型调用在 `provider.py`。

默认配置：

```text
MODEL_MODE=mock
```

所以没有密钥时会走 `generate_mock_text()`。

mock 模型支持这些场景：

- `valid_json`：合法 JSON。
- `json_with_extra_text`：JSON 前后夹自然语言。
- `missing_field`：缺字段。
- `wrong_type`：字段类型错。
- `invalid_enum`：枚举值非法。
- `broken_json`：JSON 语法坏了。

这些场景对应真实项目里经常遇到的问题。学习时不要只看成功路径，要刻意看失败路径。

如果 `.env` 改成：

```text
MODEL_MODE=deepseek
```

则会走 `generate_deepseek_text()`，通过 HTTP 调用真实模型。

## 4. JSON 解析和校验为什么分开

核心代码在 `parser.py`：

```text
parse_and_validate(raw_text)
```

它做两件事：

1. `extract_json_object(raw_text)`：把字符串解析成 Python `dict`。
2. `RefundDecision.model_validate(data)`：检查字段、类型、枚举和范围。

这两步必须分开理解。

第一步失败，说明模型输出连 JSON 语法都不成立，例如少了右花括号。

第二步失败，说明 JSON 语法没问题，但业务契约不成立，例如：

- 缺少 `confidence`。
- `missing_fields` 应该是数组却返回字符串。
- `priority` 返回了不允许的枚举值。

## 5. Agent 层如何处理失败

核心流程在 `agent.py`：

```text
run_structured_agent(case)
```

执行顺序：

```text
for attempt_number in range(1, max_attempts + 1)
-> generate_model_text()
-> parse_and_validate()
-> 成功：返回 succeeded 或 recovered
-> 失败：压缩错误，准备下一次重试
-> 重试仍失败：返回 degraded
```

`max_attempts` 来自：

```text
allow_retry = True  -> 最多 2 次
allow_retry = False -> 最多 1 次
```

这里不用 `while True`，因为 Agent 和模型调用都必须有明确上限。否则一个坏输出可能导致接口长时间卡住。

## 6. attempts 字段怎么看

接口返回里的 `attempts` 是调试线索。

每次尝试都会记录：

- `attempt_number`：第几次。
- `raw_output`：模型原始输出。
- `ok`：这次是否通过。
- `failed_stage`：失败发生在 JSON 解析还是 Pydantic 校验。
- `error`：具体错误。

真实项目里，这类信息通常会进入 trace 或日志系统。本模块先直接返回出来，方便学习者在 `/docs` 里观察。

## 7. 降级结果为什么仍然叫 decision

如果模型输出两次都失败，`agent.py` 会调用：

```text
_fallback_decision(case, reason)
```

它返回的不是随便写的错误字符串，而是一个合法的 `RefundDecision`。

关键字段是：

```text
decision_type = manual_review
risk_flags = ["structured_output_failed"]
confidence = 0
```

这样前端仍然可以按同一份结构展示结果，后续业务系统也可以把它分流给人工审核。

## 8. 本模块的完整链路

把一次请求串起来看：

```text
用户请求
-> FastAPI 请求 DTO 校验
-> provider 生成模型原始文本
-> parser 解析 JSON
-> Pydantic 校验 RefundDecision
-> 成功则返回结构化 decision
-> 失败则带错误重试一次
-> 仍失败则生成 manual_review 降级 decision
```

这条链路是后续上下文工程、状态管理、工具权限、评测和测试的基础。

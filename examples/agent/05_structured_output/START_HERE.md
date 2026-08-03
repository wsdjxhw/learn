# 先从这里学：结构化输出最小理解路径

如果你学完这个模块觉得一头雾水，先不要急着读所有代码。

这个模块只想让你先抓住一件事：

```text
模型返回的是文本，后端需要的是可信数据。
结构化输出就是把“不可信文本”变成“可信业务对象”的工程流程。
```

## 1. 先不要同时理解所有概念

第一遍只记住这 4 个角色：

```text
provider.py -> 产生模型原始文本
parser.py   -> 把文本变成 Python dict
schemas.py  -> 判断 dict 是否符合业务契约
agent.py    -> 串起调用、解析、校验、重试、降级
```

你可以先不要管 DeepSeek、JSON Schema、复杂 Agent 循环。

第一遍只看 mock 模式。

## 2. 这个模块到底在模拟什么真实问题

真实业务里，模型可能会这样输出：

```text
这个客户应该优先处理，我建议退款。
```

这句话人能懂，但程序不知道：

- 这是退款、换货还是物流问题？
- 优先级到底是 `low`、`medium` 还是 `high`？
- 要不要调用工具？
- 置信度是多少？
- 用户能看到哪句话？

所以后端要求模型返回固定结构：

```json
{
  "decision_type": "tool_call",
  "category": "refund",
  "priority": "medium",
  "confidence": 0.86
}
```

但是模型即使答了 JSON，也可能答错。

所以后端必须继续检查。

## 3. 第一遍只跑 3 个接口场景

启动服务后，只跑这 3 个场景就够了。

### 场景 A：正常输出

`mock_scenario` 使用：

```text
valid_json
```

你要观察：

```text
status = succeeded
retry_used = false
decision.decision_type = tool_call
```

这说明模型第一次输出就符合后端契约。

### 场景 B：字段缺失，但重试修复

`mock_scenario` 使用：

```text
missing_field
```

你要观察：

```text
attempts[0].ok = false
attempts[0].failed_stage = pydantic_validation
attempts[1].ok = true
status = recovered
```

这说明：

```text
JSON 能解析，不代表业务字段完整。
后端发现缺字段后，把错误反馈给模型，再让模型修一次。
```

### 场景 C：JSON 坏了，并且不重试

请求体里设置：

```json
{
  "mock_scenario": "broken_json",
  "allow_retry": false
}
```

你要观察：

```text
status = degraded
decision.decision_type = manual_review
```

这说明：

```text
模型输出彻底不可用时，接口也不能崩。
后端要返回一个稳定的降级结果。
```

## 4. 三个最容易混的概念

### JSON 解析

问题是：

```text
这段字符串能不能变成 Python dict？
```

对应文件：

```text
parser.py
```

如果模型少了右花括号，就是 JSON 解析失败。

### Pydantic 校验

问题是：

```text
这个 dict 里的字段、类型、枚举值是否符合业务要求？
```

对应文件：

```text
schemas.py
```

如果 `priority` 返回 `urgent`，但系统只允许 `low / medium / high`，就是 Pydantic 校验失败。

### 降级

问题是：

```text
模型一直输出坏结果时，接口怎么稳定返回？
```

对应文件：

```text
agent.py
```

本模块的降级策略是转人工审核：

```text
decision_type = manual_review
```

## 5. 第一遍建议阅读顺序

不要按文件名顺序读。

建议这样读：

```text
START_HERE.md
-> README.md 的“启动”和“接口测试顺序”
-> schemas.py 只看 RefundDecision
-> parser.py 只看 parse_and_validate()
-> agent.py 只看 run_structured_agent()
-> STRUCTURED_OUTPUT_EXPLAINED.md
```

`provider.py` 第一遍可以少看。你只需要知道它负责模拟模型输出。

## 6. 用一句话判断自己是否学懂

如果你能说出下面这句话，就算入门了：

```text
结构化输出不是让模型“看起来返回 JSON”，而是后端用一份契约检查模型输出，
检查失败就重试，重试失败就降级，保证接口永远返回可处理的数据结构。
```

后面再学上下文工程、记忆、工具权限、评测时，这个能力会一直被复用。

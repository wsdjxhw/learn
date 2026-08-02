# 提示词工程基础知识

## 1. 什么是 system prompt

system prompt 是发给模型的高优先级指令。

在 Agent 里，它通常负责说明：

- Agent 的角色是什么。
- 可以做什么。
- 不能做什么。
- 什么情况下必须调用工具。
- 工具调用顺序是什么。
- 最终回答应该遵守什么边界。

普通聊天里，prompt 可能只是“你是一个友好的助手”。但 Agent 里的 prompt 更像一份执行规则。

## 2. 为什么 prompt 不能一直写在代码里

如果把 prompt 写死在 Python 字符串里，会遇到几个问题：

- 改 prompt 必须改业务代码。
- 不容易知道线上现在用的是哪个版本。
- 新旧 prompt 很难对比。
- prompt 改坏后不容易回滚。
- 多人协作时不知道谁改了哪句话。

所以本模块把 prompt 放到 `prompts/` 目录里：

```text
prompts/v1_direct_answer.md
prompts/v2_tool_first.md
```

这让 prompt 像代码一样可以被版本管理。

## 3. 为什么 prompt 改动会影响工具调用

Agent 是否调用工具，经常取决于 prompt 有没有说清楚。

比如 v1 只说：

```text
当用户询问退款时，先安抚用户，并给出大致处理建议。
```

这种 prompt 很容易让模型直接回答，不去查制度，也不去计算金额。

v2 明确说：

```text
当用户问题涉及退款金额、退款资格或退款制度时，必须先使用工具。
```

这会让模型更倾向调用工具。

这就是 prompt 对 Agent 行为的影响。

## 4. 什么是 prompt 版本管理

prompt 版本管理就是：不要直接覆盖旧 prompt，而是保留多个版本。

例如：

```text
v1_direct_answer
v2_tool_first
v3_strict_refund
```

这样做有几个好处：

- 可以对比新旧版本效果。
- 新版本出问题时可以回滚。
- 可以记录每个版本解决了什么问题。
- 可以让测试用例固定跑同一个版本。

## 5. PROMPT_VERSION 解决什么问题

`.env` 里的配置：

```text
PROMPT_VERSION=v2_tool_first
```

表示默认使用哪个 prompt。

如果请求体没有传 `prompt_version`，接口会读取这个默认值。

这类似 Java 项目里用配置切换功能开关或策略版本。

## 6. 为什么本模块不用真实模型

真实模型有随机性，同一个 prompt 多跑几次也可能略有差别。

本模块的学习重点是：

- prompt 文件如何加载。
- prompt 版本如何切换。
- 如何用同一个输入对比不同 prompt。
- prompt 改动如何影响工具选择。

所以先用稳定的 mock model 更适合初学者。

后续接入真实模型时，结构仍然类似：

```text
读取 prompt 文件
-> 拼接用户输入
-> 发给模型
-> 解析模型决策
-> 执行工具
-> 记录 steps
```

区别只是 `mock_model.py` 会替换成真实 provider。

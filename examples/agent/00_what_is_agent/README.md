# 什么是 Agent

这个模块是 Agent 进阶路线的前置模块。

在学习 Tool Calling、Agent Loop、Agent 记忆之前，先回答一个更基础的问题：

```text
Agent 到底是什么？
```

本模块用一个最小可运行示例对比：

- 普通聊天接口：收到问题，直接回答。
- 最小 Agent：收到目标，思考下一步，执行动作，观察结果，再给最终回答。

## 一句话理解

在这个学习项目里，可以先把 Agent 理解成：

```text
一个围绕目标做事的 AI 后端流程。
```

它不只是“模型回答一句话”，而是多了几个关键环节：

```text
目标 -> 思考 -> 动作 -> 观察 -> 最终回答
```

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\00_what_is_agent
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

如果端口被占用：

```powershell
python -m uvicorn main:app --reload --port 8015
```

## 接口测试顺序

### 1. 健康检查

先测试：

```text
GET /health
```

确认服务能启动。

### 2. 普通聊天接口

测试：

```text
POST /chat/basic
```

请求体：

```json
{
  "message": "什么是 Agent？"
}
```

观察：它只会直接回答，不会执行动作，也没有中间步骤。

### 3. 最小 Agent 接口

测试：

```text
POST /agent/run
```

请求体：

```json
{
  "goal": "我想学习 Agent，帮我安排一个入门计划",
  "allow_action": true,
  "max_steps": 3
}
```

观察返回里的：

- `reply`：最终回答。
- `used_action`：是否执行了动作。
- `action`：执行了哪个动作。
- `steps`：Agent 的中间步骤。

### 4. 对比概念查询

请求体：

```json
{
  "goal": "Agent 和工具有什么关系？",
  "allow_action": true,
  "max_steps": 3
}
```

这个请求会触发资料查询动作。

### 5. 对比禁止动作

请求体：

```json
{
  "goal": "我想学习 Agent，帮我安排一个入门计划",
  "allow_action": false,
  "max_steps": 3
}
```

观察：`allow_action=false` 时，Agent 不会执行动作，只能直接回答。

## 本模块和 Tool Calling 的关系

这个模块只解释 Agent 的整体感觉：

```text
目标 -> 思考 -> 动作 -> 观察 -> 回答
```

下一个模块 `01_tool_calling` 才正式学习：

- 工具 schema 是什么。
- 模型如何选择工具。
- 工具参数如何生成。
- 工具执行失败如何处理。

也就是说：

```text
00_what_is_agent：先知道 Agent 是什么。
01_tool_calling：再学习 Agent 如何使用工具。
```

## 本课练习

1. 分别调用 `/chat/basic` 和 `/agent/run`，对比返回结构有什么不同。
2. 把 `/agent/run` 的 `allow_action` 改成 `false`，观察 Agent 为什么不能继续做事。
3. 用 `goal="帮我创建一个学习 Agent 的待办任务"` 测试创建待办动作。
4. 修改 `tools.py`，给 `search_agent_notes` 增加一个关键词 `记忆`，再用 `/agent/run` 验证能查到。

这些练习的重点不是改文字，而是理解 Agent 的执行链路和普通聊天接口的差别。

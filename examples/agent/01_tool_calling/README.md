# Agent 工具调用 Tool Calling

这个模块是 Agent 进阶路线的第一步。

它先不做完整 Agent Loop，只学习一件事：

```text
用户问题
-> 模型判断是否需要工具
-> 后端执行工具
-> 把工具结果整理成最终回答
```

工具调用的核心不是“模型自己执行代码”。真实流程是：模型只提出“我想调用哪个工具、参数是什么”，真正执行工具的是你的后端程序。

## 学习目标

- 理解什么是工具。
- 理解工具 schema 为什么存在。
- 理解模型如何选择工具。
- 理解工具参数从哪里来。
- 理解工具执行结果如何回到最终回答。
- 理解工具调用失败时为什么不能让接口直接崩溃。
- 区分 mock 工具调用和真实模型工具调用。

## 文件结构

```text
examples/agent/01_tool_calling
├── main.py
├── provider.py
├── tools.py
├── TOOL_CALLING_BASICS.md
├── TOOL_CALLING_EXPLAINED.md
├── README.md
├── requirements.txt
└── .env.example
```

- `main.py`：FastAPI 接口层，类似 Java Controller。
- `provider.py`：模型决策层，类似调用外部 AI 服务的 Service。
- `tools.py`：工具定义和工具执行入口。
- `TOOL_CALLING_BASICS.md`：先扫盲工具调用的基础概念。
- `TOOL_CALLING_EXPLAINED.md`：逐段解释代码结构。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\agent\01_tool_calling
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置模板：

```powershell
Copy-Item .env.example .env
```

没有 DeepSeek Key 也可以运行。没有 key 时会自动使用 mock 模式。

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

你会看到当前 provider 是 `mock` 还是 `deepseek`，以及当前工具数量。

### 2. 查看工具清单

再测试：

```text
GET /tools
```

重点观察每个工具的：

- `name`：工具名称。
- `description`：工具用途。
- `parameters`：工具参数要求。
- `required`：哪些参数必填。

### 3. 手动执行工具

测试：

```text
POST /tool/run
```

请求体示例：

```json
{
  "tool_name": "get_weather",
  "arguments": {
    "city": "深圳"
  }
}
```

再试一个计算工具：

```json
{
  "tool_name": "calculate_order_total",
  "arguments": {
    "item_price": 19.9,
    "quantity": 3,
    "discount_code": "SAVE10"
  }
}
```

### 4. 通过聊天接口触发工具

测试：

```text
POST /chat
```

天气问题：

```json
{
  "message": "深圳今天会下雨吗？"
}
```

订单计算：

```json
{
  "message": "单价 19.9 元的商品买 3 个，用 SAVE10 优惠码，总价是多少？"
}
```

制度检索：

```json
{
  "message": "报销制度是什么？"
}
```

不需要工具的问题：

```json
{
  "message": "什么是工具调用？"
}
```

## 观察响应

重点看 `/chat` 返回里的几个字段：

- `reply`：最终给用户看的回答。
- `used_tool`：这次是否真的执行了工具。
- `tool_name`：执行了哪个工具。
- `tool_output`：工具返回的结构化结果。
- `steps`：中间步骤记录。

`steps` 是本模块最重要的学习材料。它能让你看到：

```text
user_input -> model_decision -> tool_execution -> final_answer
```

这就是后续 Agent Loop 的基础。

## 有 DeepSeek Key 时

编辑 `.env`：

```text
DEEPSEEK_API_KEY=你的 deepseek key
DEEPSEEK_MODEL=deepseek-v4-flash
```

有 key 时，`provider.py` 会把 `tools.py` 里的工具 schema 传给 DeepSeek，让模型自己决定是否返回工具调用。

注意：即使模型决定调用工具，工具仍然由本地 Python 后端执行。模型不会直接访问你的数据库、文件或内部系统。

## 本课练习

1. 先用 `/tool/run` 手动调用 `get_weather`，传入一个不支持的城市，观察错误结构。
2. 再用 `/chat` 问同一个不支持城市的天气，思考为什么 mock 决策没有调用工具。
3. 调用 `calculate_order_total` 时传入 `quantity=0`，观察工具如何返回失败。
4. 给 `search_policy` 增加一个关键词，例如 `加班`，并用 `/chat` 验证能查到。
5. 对比 `allow_tool=true` 和 `allow_tool=false` 的返回，理解工具开关的作用。

这些练习对应真实开发能力：参数校验、错误处理、工具白名单、状态观察和接口链路追踪。

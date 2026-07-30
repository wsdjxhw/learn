# 认证、限流和日志代码讲解

本模块接在聊天、数据库、RAG、后台任务和流式输出之后。

它解决的问题不是“怎么让模型更聪明”，而是：

```text
怎么让一个 AI API 可以被真实使用、排查和控制
```

## 文件职责

```text
main.py      FastAPI 接口层、统一错误响应、中间件
config.py    读取 .env 配置
security.py  API Key 鉴权和简单限流
database.py  SQLite 日志表和查询函数
provider.py  mock / DeepSeek 模型调用和教学版成本估算
```

类比 Java：

- `main.py` 类似 Controller + Filter 配置。
- `security.py` 类似鉴权 Filter 或 Interceptor。
- `database.py` 类似 Repository。
- `provider.py` 类似调用外部模型服务的 Service。
- `ChatRequest` 类似请求 DTO。

## 两种 API Key

本模块刻意区分两种 key：

```text
APP_API_KEYS      调用你这个 FastAPI 服务的 key
DEEPSEEK_API_KEY 你的服务调用 DeepSeek 的 key
```

这两个 key 不应该混用。

用户或前端只应该知道 `APP_API_KEYS` 里的某一个 key。`DEEPSEEK_API_KEY` 应该只保存在服务端。

## `Header(...)` 参数从哪里来

`security.py` 里：

```python
def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthContext:
```

`Header(...)` 告诉 FastAPI：

```text
x_api_key 不是路径参数
不是查询参数
不是请求体
而是 HTTP Header 里的 X-API-Key
```

所以客户端要这样传：

```text
X-API-Key: dev-key-123
```

## `Depends()` 怎么理解

`main.py` 里：

```python
rate: RateLimitContext = Depends(limited_context)
```

可以理解成 FastAPI 自动帮你执行：

```text
limited_context()
-> require_api_key()
-> check_rate_limit()
```

如果中间任何一步失败，接口函数就不会继续执行。

这和 Java 里的 Filter、Interceptor、AOP 前置校验有点像。

## 为什么日志里不保存原始 API Key

`security.py` 里：

```python
hash_api_key(api_key)
```

日志里保存的是 hash 后的前 12 位，不是原始 key。

原因是：

```text
日志经常会被更多系统或人员查看
如果日志里有原始 API Key，泄露风险很高
```

保留短 hash 仍然可以区分调用方，又不会让别人拿日志里的值直接调用 API。

## 限流怎么工作

本模块使用一个内存字典：

```python
REQUEST_BUCKETS: dict[str, list[float]] = {}
```

结构可以理解成：

```text
api_key_hash -> 最近一分钟内的请求时间列表
```

每次请求：

1. 删除 60 秒以前的时间。
2. 看剩下的请求次数是否超过上限。
3. 没超过就把当前时间加入列表。
4. 超过就返回 429。

这叫滑动窗口限流的简化版。

真实项目通常会把这个状态放进 Redis，因为多个进程和多台服务器之间不能共享 Python 内存字典。

## middleware 请求日志

`main.py` 里：

```python
@app.middleware("http")
async def request_logging_middleware(...)
```

middleware 会包住每一次请求：

```text
请求进入
-> 记录开始时间
-> 执行具体接口
-> 拿到状态码
-> 计算耗时
-> 写入 request_logs
```

所以即使接口返回 401、403、429，也会留下请求记录。

## 统一错误响应

FastAPI 默认错误格式通常是：

```json
{"detail": "..."}
```

本模块改成：

```json
{
  "error": {
    "type": "http_error",
    "message": "...",
    "status_code": 400
  }
}
```

这能让前端处理错误更稳定。

同时错误会写入 `error_logs`，方便后续排查。

## 模型调用日志

`POST /chat` 成功后会写入 `model_call_logs`：

```text
provider
model
success
prompt_chars
reply_chars
estimated_input_tokens
estimated_output_tokens
estimated_cost_usd
```

这类日志解决的是：

```text
到底调用了几次模型？
哪次失败了？
大概用了多少 token？
估算成本是多少？
```

本模块里的成本是教学估算，不是真实账单。

真实项目应该优先使用模型服务商返回的 usage，并按照实际价格计算。

## 日志查询接口

本模块提供：

```text
GET /logs/requests
GET /logs/errors
GET /logs/model-calls
GET /stats/costs
```

这些接口也需要 `X-API-Key`。

但它们没有使用限流依赖，只使用鉴权依赖。原因是：排查问题时，如果日志接口也被同一个限流挡住，会让调试更困难。

这就是一个小型设计判断：

```text
不是所有接口都应该套同一套限流规则
```

## 本模块真正要掌握什么

学完这个模块后，应该能说清楚：

- 为什么外部模型 key 不能直接暴露给前端。
- `X-API-Key` 从哪里来。
- `Depends()` 如何串起鉴权和限流。
- 401、403、429 分别代表什么。
- 为什么要统一错误响应。
- 请求日志、错误日志、模型调用日志分别解决什么问题。
- 为什么成本记录是 AI API 的基础可观测性之一。

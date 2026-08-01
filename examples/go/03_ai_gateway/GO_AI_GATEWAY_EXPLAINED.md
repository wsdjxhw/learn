# Go AI 网关代码讲解

这个模块的代码结构：

```text
main.go      -> 程序入口，组装配置、客户端、路由
config.go    -> 读取 .env 和环境变量
types.go     -> 定义请求和响应结构
client.go    -> 调用 Python AI 后端或 mock 回复
handlers.go  -> HTTP 接口处理函数
```

## 1. `main.go`：程序入口

`main()` 只做四件事：

```text
读取配置 -> 创建 AIClient -> 注册路由 -> 启动服务
```

这和前面 Python 模块里的 `main.py` 职责类似：入口文件负责把各层连接起来，不应该塞满业务细节。

## 2. `config.go`：配置从哪里来

`LoadConfig(".env")` 会先读取 `.env`，再读取系统环境变量。

系统环境变量优先级更高，原因是部署时 Docker、服务器、CI 通常会直接注入环境变量，而不是修改代码文件。

关键配置：

- `GO_GATEWAY_PORT`：Go 网关监听端口。
- `AI_BACKEND_URL`：Python AI 服务地址。
- `AI_BACKEND_CHAT_PATH`：Python 聊天接口路径。
- `AI_BACKEND_API_KEY`：转发给 Python 服务的 `X-API-Key`。
- `AI_BACKEND_MOCK`：是否走 mock。
- `MAX_BATCH_SIZE`：批量接口的最大消息数。

`readDotEnvFile()` 是教学版 dotenv 解析器，只支持最常见的 `KEY=value`。真实项目可以换成成熟 dotenv 库。

## 3. `types.go`：DTO 和 JSON 结构

`ChatRequest`：

```go
type ChatRequest struct {
    Message      string `json:"message"`
    SystemPrompt string `json:"system_prompt"`
}
```

它类似 Java 请求 DTO，也类似前面 FastAPI 里的 Pydantic `BaseModel`。它描述调用方传入的 JSON，而不是数据库表。

`ChatResponse` 是网关统一返回给调用方的结构。里面的 `Source` 字段用来观察这次回复来自：

```text
go-mock
python-backend
```

## 4. `client.go`：后端调用层

`AIClient.GenerateReply()` 是这个模块的核心分层点。

handler 不直接调用 Python 服务，而是调用：

```go
reply, err := server.client.GenerateReply(request.Context(), payload)
```

好处是：

- HTTP handler 只关心请求和响应。
- Python 后端怎么调用，集中放在 `client.go`。
- 后续增加重试、超时、日志，也可以集中改这里。

`shouldUseMock()` 的规则：

```text
AI_BACKEND_MOCK=true -> mock
AI_BACKEND_URL 为空 -> mock
否则 -> 调 Python 后端
```

这保证没有 Python 服务时也能跑通。

## 5. 转发请求的流程

真实转发时，流程是：

```text
ChatRequest struct
-> json.Marshal 变成 JSON 字节
-> http.NewRequestWithContext 创建 POST 请求
-> http.Client.Do 发送到 Python 服务
-> io.ReadAll 读取响应体
-> json.Unmarshal 解成 BackendChatResponse
-> 转成 ChatResponse 返回给调用方
```

`request.Context()` 会把客户端请求的上下文传下去。如果调用方断开连接，后端调用也有机会被取消。

## 6. `handlers.go`：HTTP 接口层

`RegisterRoutes()` 注册三个接口：

```text
GET  /health
POST /gateway/chat
POST /gateway/batch-chat
```

`chatHandler()` 的主要流程：

```text
检查 HTTP 方法
-> 解 JSON 请求体
-> 校验 message 不能为空
-> 补默认 system_prompt
-> 调 AIClient
-> 返回 JSON
```

这里能对应前面 FastAPI 的接口函数，只是 Go 写法更显式。

## 7. `batchChatHandler()`：并发任务

批量接口先校验：

```text
messages 不能为空
messages 数量不能超过 MAX_BATCH_SIZE
```

然后对每条非空消息启动一个 goroutine。

`sync.WaitGroup` 的作用是等待所有 goroutine 都结束，再统一返回结果。可以类比 Java 里等待多个 Future 完成。

特别注意这段设计：

```text
某一条消息失败 -> 只写入这一条 item 的 error
整个 batch 请求仍然返回其他成功结果
```

这是真实工程里常见的“局部失败隔离”。

## 8. `loggingMiddleware()`：最小日志

middleware 可以理解成 Java Web 的 Filter。

每个请求都会经过它：

```text
记录开始时间
-> 执行真实 handler
-> 记录方法、路径、状态码、耗时
```

当前只是打印日志。后续可以扩展成写入文件、数据库或可观测性系统。

## 9. 当前模块的学习重点

读代码时建议按这个顺序：

1. 从 `main.go` 看服务怎么启动。
2. 看 `types.go` 理解输入输出 JSON。
3. 看 `handlers.go` 理解接口流程。
4. 看 `client.go` 理解 mock 和真实后端切换。
5. 看 `batchChatHandler()` 理解 goroutine 和 WaitGroup。

不要一开始就纠结 Go 框架。先看懂标准库版本，后面再学 Gin、Echo 或真实 API Gateway 会更稳。

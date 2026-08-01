# Go AI 网关

这一节的目标：理解 Go 在 AI 应用里适合承担什么后端角色。

前面的主线主要是 Python：

```text
FastAPI -> 数据库 -> RAG -> 后台任务 -> 前端 -> Docker
```

这个模块换成 Go，不是为了替代 Python AI 服务，而是学习一种常见分工：

```text
前端 / 调用方 -> Go 网关 -> Python AI 服务
```

Go 网关负责接收请求、做统一入口、转发到 Python 服务，也可以做并发批量调用。真正的模型调用、RAG、数据库逻辑仍然可以留在 Python 服务里。

## 先读

如果你没有 Go 基础，先回到上一层目录按顺序读：

- [../GO_MINIMAL_BASICS.md](../GO_MINIMAL_BASICS.md)
- [../01_STRUCT_AND_SLICE_EXPLAINED.md](../01_STRUCT_AND_SLICE_EXPLAINED.md)
- [../02_HTTP_SERVER_EXPLAINED.md](../02_HTTP_SERVER_EXPLAINED.md)

先跑通 `01_struct_and_slice.go` 和 `02_http_server.go`，再进入网关会更顺。

基础知识：

[GO_GATEWAY_BASICS.md](GO_GATEWAY_BASICS.md)

代码讲解：

[GO_AI_GATEWAY_EXPLAINED.md](GO_AI_GATEWAY_EXPLAINED.md)

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\go\03_ai_gateway
```

复制配置：

```powershell
Copy-Item .env.example .env
```

默认配置会走 mock 模式，不需要启动 Python 后端。

启动 Go 网关：

```powershell
go run .
```

服务默认运行在：

```text
http://127.0.0.1:8081
```

如果端口被占用，修改 `.env`：

```text
GO_GATEWAY_PORT=8082
```

## 测试顺序

1. `GET /health`
2. `POST /gateway/chat`
3. `POST /gateway/batch-chat`
4. 启动 Python AI 服务后，把 `.env` 改成真实转发模式，再测一次 `/gateway/chat`。

## `POST /gateway/chat` 示例

PowerShell：

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8081/gateway/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Go 网关在 AI 应用里解决什么问题？"}'
```

返回里重点看：

- `reply`：mock 或 Python 后端返回的回答。
- `provider`：当前提供回复的是 mock 还是真实后端。
- `source`：这次结果来自 `go-mock` 还是 `python-backend`。

## `POST /gateway/batch-chat` 示例

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8081/gateway/batch-chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"messages":["解释网关","解释并发","解释转发"]}'
```

这个接口会用 goroutine 并发处理多条消息。学习重点不是“批量聊天”本身，而是观察 Go 如何并发等待多个后端调用。

## 接入 Python AI 服务

先启动一个已有 Python 模块，例如：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\01_chat_api
python -m uvicorn main:app --reload
```

再把本模块 `.env` 改成：

```text
AI_BACKEND_URL=http://127.0.0.1:8000
AI_BACKEND_CHAT_PATH=/chat
AI_BACKEND_MOCK=false
```

如果接的是 `examples/ai/10_auth_rate_limit_logging`，还需要：

```text
AI_BACKEND_API_KEY=dev-key-123
```

这样 Go 网关会自动把 `X-API-Key` 转发给 Python 服务。

## 当前实现边界

本模块为了学习清晰，先使用：

- Go 标准库 `net/http`，不引入 Gin、Echo 等框架。
- 简单 `.env` 解析，不引入第三方 dotenv 库。
- mock 模式保证无 Python 服务也能跑通。
- `/gateway/batch-chat` 演示 goroutine 并发。

真实项目后续会继续升级：

- 鉴权、限流、日志和 trace。
- 更严格的超时、重试、熔断。
- 服务发现或负载均衡。
- OpenAPI 文档或统一 API 网关配置。

## 本课练习

1. 不启动 Python 服务，直接跑 Go 网关，确认 `/health` 显示 `mock_mode: true`。
2. 调用 `/gateway/chat`，说明请求输入、Go 处理、返回输出分别是什么。
3. 把 `AI_BACKEND_MOCK=false` 但不配置 `AI_BACKEND_URL`，观察为什么仍然走 mock。
4. 启动 `examples/ai/01_chat_api`，让 Go 网关转发到 Python `/chat`。
5. 调用 `/gateway/batch-chat`，对比它和单条 `/gateway/chat` 的返回结构。
6. 故意传一个空字符串到 batch 里，观察单条失败不会导致整个批量请求失败。
7. 设计一个扩展：让 Go 网关只允许带 `X-Gateway-Key` 的调用方访问，但不要把这个 key 传给 Python 后端。

这些练习的目标是理解 Go 网关的真实工程价值：统一入口、隐藏内部服务、转发请求、并发处理和错误隔离。

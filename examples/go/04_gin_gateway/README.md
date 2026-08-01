# Gin 网关基础

这一节的目标：在已经看过 Go 标准库 `net/http` 之后，理解 Gin 框架帮我们简化了什么。

这个模块不接真实 Python 后端，也不影响 Python AI 主线。它只做一件事：

```text
用 Gin 写一组 AI 网关风格的 HTTP 接口
```

先看标准库版本，再看 Gin 版本，学习效果会更好：

```text
../02_http_server
-> 当前模块 04_gin_gateway
-> ../03_ai_gateway
```

## 先读

基础知识：

[GIN_BASICS.md](GIN_BASICS.md)

代码讲解：

[GIN_GATEWAY_EXPLAINED.md](GIN_GATEWAY_EXPLAINED.md)

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\go\04_gin_gateway
```

下载依赖：

```powershell
go mod tidy
```

启动服务：

```powershell
go run .
```

服务默认运行在：

```text
http://127.0.0.1:8081
```

## 测试顺序

1. `GET /api/health`
2. `GET /api/hello?name=Tom`
3. `GET /api/messages/101`
4. `POST /api/chat-preview`
5. 给 `/api/chat-preview` 传空 message，观察统一错误响应。

## 请求示例

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8081/api/health
```

query 参数：

```powershell
Invoke-RestMethod "http://127.0.0.1:8081/api/hello?name=Tom"
```

path 参数：

```powershell
Invoke-RestMethod http://127.0.0.1:8081/api/messages/101
```

JSON 请求体：

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8081/api/chat-preview `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Gin 如何简化 Go HTTP 接口？"}'
```

## 这个模块到底学什么

- `gin.Default()`：创建带日志和恢复能力的 Gin 路由器。
- `router.Group("/api")`：路由分组。
- `api.GET()` / `api.POST()`：注册接口。
- `*gin.Context`：Gin handler 里的请求上下文。
- `context.Query()` / `context.DefaultQuery()`：读取 query 参数。
- `context.Param()`：读取 path 参数。
- `context.ShouldBindJSON()`：读取 JSON 请求体。
- `context.JSON()`：返回 JSON 响应。
- middleware：在接口前后统一处理公共逻辑。

## 当前实现边界

本模块为了零基础可读：

- 不接真实 Python AI 服务。
- 不做数据库。
- 不做真实鉴权。
- 不引入复杂项目分层。

它先解决一个问题：

```text
标准库能写 HTTP 服务，那 Gin 到底让哪些代码变短、变清楚？
```

## 本课练习

1. 用 `POST` 请求 `/api/health`，观察 Gin 自动返回 404/405 这类路由结果。
2. 调 `/api/hello?name=`，观察默认值如何生效。
3. 调 `/api/messages/abc-123`，说明 `abc-123` 是从哪里进入代码的。
4. 给 `/api/chat-preview` 传 `{}`，观察 `ShouldBindJSON` 的错误处理。
5. 给 `/api/chat-preview` 传 `"   "`，说明为什么还需要 `strings.TrimSpace()`。
6. 新增一个 `/api/gateway/status` 接口，返回 `{"status":"ready"}`，并说明它应该放在 `/api` 分组下还是单独分组。

这些练习的目标是理解 Gin 的路由、参数、请求体、响应和 middleware，而不是只复制接口。

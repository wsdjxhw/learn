# Gin 网关代码讲解

对应代码：

[main.go](main.go)

## 代码结构

这个模块故意先只放一个 `main.go`。

原因是学习 Gin 时，第一目标不是项目分层，而是看懂 Gin 的核心写法：

```text
创建 router
-> 注册 middleware
-> 创建路由分组
-> 注册 GET / POST
-> 读取参数
-> 返回 JSON
```

等这些概念稳定之后，再像 `03_ai_gateway` 那样拆成 `config.go`、`client.go`、`handlers.go`。

## 1. 请求和响应结构

`ChatPreviewRequest` 是请求 DTO：

```go
type ChatPreviewRequest struct {
    Message string `json:"message" binding:"required"`
}
```

它说明调用方必须传：

```json
{
  "message": "..."
}
```

`binding:"required"` 是 Gin 的校验规则。字段缺失时，`ShouldBindJSON` 会返回错误。

但注意：

```json
{
  "message": "   "
}
```

这种全空格字符串仍然算传了字段，所以代码里还要用 `strings.TrimSpace()` 做业务校验。

## 2. `main()`

```go
router := setupRouter()
router.Run(":8081")
```

`setupRouter()` 负责创建和配置路由。

`router.Run(":8081")` 启动服务。

8081 是为了避免和标准库 HTTP 示例的 8080 冲突。

## 3. `setupRouter()`

```go
router := gin.Default()
router.Use(requestIDMiddleware())
api := router.Group("/api")
```

这三行分别做：

```text
创建 Gin 路由器
-> 注册全局 middleware
-> 创建 /api 路由分组
```

分组里的接口：

```text
GET  /api/health
GET  /api/hello
GET  /api/messages/:message_id
POST /api/chat-preview
```

## 4. `requestIDMiddleware()`

middleware 的职责不是处理某个具体业务，而是处理公共逻辑。

这里做了三件事：

```text
生成 request_id
-> 放进 Gin Context
-> 调 context.Next() 继续执行后面的 handler
```

关键点：

```go
context.Set("request_id", requestID)
context.Next()
```

后面的 handler 可以通过：

```go
context.GetString("request_id")
```

把同一个 request_id 取出来。

这能帮助你理解：Gin 的 Context 不只是请求参数容器，也可以在 middleware 和 handler 之间传递数据。

## 5. `healthHandler()`

```go
context.JSON(http.StatusOK, HealthResponse{...})
```

Gin 的 `context.JSON()` 会帮你：

```text
设置 Content-Type
设置状态码
把 struct 转成 JSON
```

所以不需要像标准库那样手写 `json.NewEncoder()`。

## 6. `helloHandler()`

```go
name := strings.TrimSpace(context.DefaultQuery("name", "world"))
```

参数来源是 URL query：

```text
/api/hello?name=Tom
```

如果调用方没有传 name，就使用默认值 `world`。

## 7. `messageDetailHandler()`

路由：

```go
api.GET("/messages/:message_id", messageDetailHandler)
```

请求：

```text
GET /api/messages/101
```

读取：

```go
messageID := context.Param("message_id")
```

这个示例是为了区分：

```text
query 参数：?name=Tom
path 参数：/messages/101
```

## 8. `chatPreviewHandler()`

这是最接近后续网关接口的 handler。

流程：

```text
声明 payload
-> ShouldBindJSON 读取请求体
-> TrimSpace 校验空字符串
-> 返回预览结果
```

如果请求体不是合法 JSON，或者缺少 `message` 字段，会返回 400。

如果 `message` 只有空格，也返回 400。

这对应真实工程里的输入校验。

## 9. `writeError()`

错误响应统一使用：

```json
{
  "error": "...",
  "request_id": "..."
}
```

统一错误结构的好处是：前端不用猜错误字段到底叫 `detail`、`message` 还是 `error`。

## 10. 和 `net/http` 版本对比

标准库版本里，你需要手动处理：

```text
判断 HTTP 方法
设置 JSON Header
写状态码
json.NewEncoder
从 request.URL.Query() 取 query
从 request.Body 解 JSON
```

Gin 简化成：

```text
api.GET / api.POST
context.JSON
context.DefaultQuery
context.Param
context.ShouldBindJSON
middleware
```

这就是本模块的学习重点。

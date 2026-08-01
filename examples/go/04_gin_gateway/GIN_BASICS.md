# Gin 基础

## Gin 是什么

Gin 是 Go 里的 Web 框架。

可以类比：

```text
Python: FastAPI
Java: Spring MVC / Spring Boot Controller
Go: Gin
```

它不是 Go 语言本身，而是基于 Go 标准库 `net/http` 封装出来的一层框架。

## 为什么不一开始就学 Gin

前一个模块先学 `net/http`，是为了看清 HTTP 服务的底层流程：

```text
请求进来
-> handler 处理
-> 读取 query / body
-> 写 JSON 响应
```

Gin 会把很多重复代码变短。

如果完全没看过标准库，直接学 Gin，容易只记住框架写法，但不知道它帮你省掉了什么。

## `gin.Default()`

```go
router := gin.Default()
```

这行代码创建一个 Gin 路由器。

它默认带两个常用 middleware：

- Logger：打印每个请求的日志。
- Recovery：handler 崩溃时尽量让服务不直接退出。

可以先理解成 Spring Boot 帮你准备好了 Web 应用的基础运行环境。

## `gin.Context`

Gin handler 通常长这样：

```go
func helloHandler(context *gin.Context) {
    context.JSON(200, gin.H{"message": "hello"})
}
```

`*gin.Context` 里包含当前请求相关的信息，也提供写响应的方法。

它大致替代了标准库里的两个参数：

```go
writer http.ResponseWriter
request *http.Request
```

所以 Gin handler 看起来更短。

## 路由

标准库写法：

```go
mux.HandleFunc("/health", healthHandler)
```

Gin 写法：

```go
router.GET("/health", healthHandler)
router.POST("/chat-preview", chatPreviewHandler)
```

Gin 把 HTTP 方法直接写在路由注册里，可读性更强。

## query 参数

请求：

```text
GET /api/hello?name=Tom
```

Gin 读取：

```go
name := context.DefaultQuery("name", "world")
```

如果没有传 `name`，默认值就是 `world`。

## path 参数

路由：

```go
GET /api/messages/:message_id
```

请求：

```text
GET /api/messages/101
```

Gin 读取：

```go
messageID := context.Param("message_id")
```

path 参数适合表示“我要操作哪个资源”。

## JSON 请求体

请求体：

```json
{
  "message": "hello"
}
```

Gin 读取：

```go
var payload ChatPreviewRequest
if err := context.ShouldBindJSON(&payload); err != nil {
    // 处理错误
}
```

`ShouldBindJSON` 会把 JSON 字段填进 struct。

`&payload` 表示传地址，让函数可以修改 payload。

## JSON 响应

Gin 返回 JSON：

```go
context.JSON(http.StatusOK, response)
```

它会自动设置 JSON 响应头，并把 struct 编码成 JSON。

这比标准库里手写：

```go
writer.Header().Set("Content-Type", "application/json")
json.NewEncoder(writer).Encode(response)
```

更短。

## 路由分组

```go
api := router.Group("/api")
api.GET("/health", healthHandler)
```

实际路径是：

```text
/api/health
```

分组适合把一批相关接口放在一起。以后做网关时，可以有：

```text
/api
/admin
/internal
```

## middleware

middleware 是请求进入 handler 前后执行的公共逻辑。

可以类比 Java Web Filter。

常见用途：

- 打日志。
- 生成 request_id。
- 鉴权。
- 限流。
- 统一处理异常。

本模块的 middleware 会给每个请求生成一个 `request_id`，后面的 handler 再把它放进响应里，方便你观察“同一次请求的数据如何在上下文里传递”。

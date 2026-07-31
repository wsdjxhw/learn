# 02 Go HTTP 服务代码讲解

对应代码：

[02_http_server.go](02_http_server.go)

## 这个示例教什么

这个示例教 Go 如何把代码变成 HTTP 接口。

它是 `03_ai_gateway` 的前置知识：

```text
先会接收 HTTP 请求
-> 再学把请求转发给 Python AI 服务
```

## 导入包

```go
import (
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "strings"
)
```

这些都是 Go 标准库：

- `encoding/json`：处理 JSON。
- `fmt`：格式化字符串。
- `log`：打印服务日志。
- `net/http`：启动 HTTP 服务。
- `strings`：处理字符串空格。

## 请求 DTO

```go
type ChatRequest struct {
    Message string `json:"message"`
}
```

`ChatRequest` 类似 Java 请求 DTO，也类似 FastAPI 里的 `BaseModel`。

调用方传：

```json
{
  "message": "hello"
}
```

Go 会把它解码到 `payload.Message`。

## 响应结构

示例里没有直接返回散乱的 map，而是定义了：

- `HealthResponse`
- `HelloResponse`
- `ChatPreviewResponse`
- `ErrorResponse`

这样做是为了让输入输出结构稳定。真实前端或调用方才能按固定字段解析结果。

## `writeJSON()`

这个函数统一写 JSON 响应。

流程是：

```text
设置 Content-Type
-> 写 HTTP 状态码
-> 把 Go struct 编码成 JSON
```

`value interface{}` 表示这里可以接收不同类型的响应结构。

初学阶段可以先把 `interface{}` 理解成“任意类型”。后续 Go 进阶再系统学接口。

## `healthHandler()`

这个接口用于确认服务是否启动。

只允许 GET：

```go
if request.Method != http.MethodGet
```

如果别人用 POST 调 `/health`，就返回 405。

这对应真实工程里的“接口方法校验”。

## `helloHandler()`

这个接口演示 query 参数。

请求：

```text
GET /hello?name=Tom
```

代码：

```go
name := strings.TrimSpace(request.URL.Query().Get("name"))
```

参数来源是 URL，不是请求体。

如果 `name` 为空，默认用 `world`，这是一个最小的空数据处理。

## `chatPreviewHandler()`

这个接口演示 POST JSON 请求体。

流程：

```text
检查必须是 POST
-> 解码 JSON body
-> 校验 message 不能为空
-> 返回预览结果
```

关键代码：

```go
json.NewDecoder(request.Body).Decode(&payload)
```

`request.Body` 是请求体。

`&payload` 是把 payload 的地址传进去，让 Decode 能把 JSON 字段写入 payload。

## `main()`

`main()` 负责注册路由并启动服务：

```go
mux := http.NewServeMux()
mux.HandleFunc("/health", healthHandler)
mux.HandleFunc("/hello", helloHandler)
mux.HandleFunc("/chat-preview", chatPreviewHandler)
http.ListenAndServe(address, mux)
```

`ServeMux` 可以理解成路由表。

`ListenAndServe` 会启动 HTTP 服务，并一直运行。

## 测试顺序

启动：

```powershell
go run 02_http_server.go
```

测试健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

测试 query 参数：

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/hello?name=Tom"
```

测试 JSON 请求体：

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/chat-preview `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Go 如何接收 JSON 请求？"}'
```

## 练习

1. 用 POST 调 `/health`，观察 405 错误。
2. 用 `/hello?name=` 调接口，观察默认值。
3. 给 `/chat-preview` 传 `{}`，观察 400 错误。
4. 给 `ChatPreviewResponse` 增加 `should_forward bool` 字段：当 message 长度大于 5 时为 true。
5. 解释 `/hello` 的输入来自 query，而 `/chat-preview` 的输入来自 request body。

这些练习对应真实开发能力：方法校验、参数来源区分、请求体解析、错误响应、字段扩展。

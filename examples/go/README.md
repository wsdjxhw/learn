# Go 后端补充

Go 这一块不替代 Python AI 主线。

它的定位是：在已经理解 AI 应用后端地基之后，补一条最小 Go 后端路线，让你知道 Go 可以怎样承担服务入口、HTTP 转发和并发处理这些工程角色。

推荐顺序：

```text
01_struct_and_slice.go
-> 02_http_server.go
-> 03_ai_gateway
```

## 先读

Go 最小基础：

[GO_MINIMAL_BASICS.md](GO_MINIMAL_BASICS.md)

Go 学习规划：

[GO_LEARNING_PLAN.md](GO_LEARNING_PLAN.md)

## 1. 结构体、切片和函数

代码：

[01_struct_and_slice.go](01_struct_and_slice.go)

讲解：

[01_STRUCT_AND_SLICE_EXPLAINED.md](01_STRUCT_AND_SLICE_EXPLAINED.md)

运行：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\go
go run 01_struct_and_slice.go
```

学习目标：

- 理解 `package main`
- 理解 `import`
- 理解 `func main()`
- 理解 `struct` 类似 Java DTO / POJO
- 理解 slice 类似 Java ArrayList
- 理解 `for range`
- 理解函数参数和返回值

## 2. Go HTTP 服务

代码：

[02_http_server.go](02_http_server.go)

讲解：

[02_HTTP_SERVER_EXPLAINED.md](02_HTTP_SERVER_EXPLAINED.md)

运行：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\go
go run 02_http_server.go
```

测试顺序：

1. `GET http://127.0.0.1:8080/health`
2. `GET http://127.0.0.1:8080/hello?name=Tom`
3. `POST http://127.0.0.1:8080/chat-preview`
4. 给 `/chat-preview` 传空 message，观察错误返回。

PowerShell 示例：

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/chat-preview `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Go 如何接收 JSON 请求？"}'
```

学习目标：

- 理解 `net/http`
- 理解 handler 函数
- 理解 query 参数从哪里来
- 理解 JSON 请求体如何进入 struct
- 理解统一 JSON 响应和错误响应
- 为 `03_ai_gateway` 的请求转发做准备

## 3. Go AI 网关

模块：

[03_ai_gateway](03_ai_gateway)

学习目标：

- 理解 Go 作为 AI 服务网关
- 理解 mock 和真实 Python 后端切换
- 理解 HTTP 请求转发
- 理解 goroutine 并发批量调用

## 当前边界

这条 Go 路线先不系统展开完整 Go 语言，也不立刻引入 Gin。

顺序应该是：

```text
先看懂标准库 HTTP
-> 再看懂网关转发
-> 最后再考虑 Gin、微服务、服务发现、熔断、追踪
```

这样不会影响 Python AI 主线，也不会让初学者一开始就被框架概念淹没。

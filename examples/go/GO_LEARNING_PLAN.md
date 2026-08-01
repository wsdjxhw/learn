# Go 补充学习规划

这条路线只服务 AI 应用后端学习，不影响 Python 主线。

Python 主线仍然是：

```text
FastAPI -> DeepSeek -> 数据库 -> RAG -> 后台任务 -> 生产化 -> Agent
```

Go 放在这条主线之后，作为后端服务能力补充。

## 阶段 G1：Go 最小语法

对应：

- [01_struct_and_slice](01_struct_and_slice)
- [01_STRUCT_AND_SLICE_EXPLAINED.md](01_STRUCT_AND_SLICE_EXPLAINED.md)

目标：

- 能运行一个 Go 文件。
- 理解 `package main` 和 `func main()`。
- 理解 `struct`、slice、函数、`if`、`for range`。
- 能把用户问题整理成一个输出结构。

这一阶段不讲：

- goroutine。
- channel。
- interface 设计。
- 泛型。
- 项目工程化。

## 阶段 G2：Go HTTP 服务

对应：

- [02_http_server](02_http_server)
- [02_HTTP_SERVER_EXPLAINED.md](02_HTTP_SERVER_EXPLAINED.md)

目标：

- 能启动一个 Go HTTP 服务。
- 理解 handler 的 `writer` 和 `request`。
- 理解 query 参数。
- 理解 JSON 请求体。
- 理解错误响应。

这一阶段先用标准库 `net/http`，不引入 Gin。

原因是要先看清 HTTP 服务的底层流程。

## 阶段 G3：Go AI 网关

对应：

- [03_ai_gateway](03_ai_gateway)

目标：

- 理解 Go 作为统一入口。
- 理解 Go 如何转发请求到 Python AI 服务。
- 理解 mock 模式和真实后端切换。
- 理解 goroutine 并发处理 batch 请求。
- 理解 Go 和 Python 的后端分工。

## 阶段 G4：Gin 框架

对应：

- [04_gin_gateway](04_gin_gateway)

目标：

- 用 Gin 重写标准库 HTTP 示例里的常见接口写法。
- 理解 `gin.Context`。
- 理解 `c.ShouldBindJSON()`。
- 理解 `c.JSON()`。
- 理解 Gin middleware。
- 理解路由分组。

Gin 应该放在标准库之后学。否则初学者容易会写框架代码，但不知道 HTTP 请求和响应到底发生了什么。

## 阶段 G5：更真实的网关能力

未来可以继续补：

- 网关鉴权。
- 网关限流。
- 请求日志和 trace id。
- 超时和重试。
- 多个 Python 后端服务的路由转发。
- Docker 部署 Go 网关。

## 当前学习原则

每一步都要先能运行，再解释输入、处理、输出。

Go 部分的目标不是炫技，而是让你能回答：

```text
如果 Python AI 服务已经能工作了，Go 还能在系统里解决什么工程问题？
```

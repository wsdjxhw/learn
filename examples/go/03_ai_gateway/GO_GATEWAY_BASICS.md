# Go 网关基础

## Go 在这条路线里的位置

前面已经学过 Python AI 应用后端：

```text
FastAPI 接口
-> DeepSeek 调用
-> 数据库
-> RAG
-> 后台任务
-> 前端页面
-> Docker 部署
```

Go 这一节不是重新写一套 AI 应用，而是学习后端服务里的另一种常见角色：网关。

## 什么是网关

网关可以理解成系统入口。

调用方不直接访问所有内部服务，而是先访问网关：

```text
调用方 -> Go 网关 -> Python AI 服务
```

这样做有几个好处：

- 调用方只记住一个入口。
- 内部 Python 服务地址可以隐藏。
- 鉴权、限流、日志以后可以集中放在网关。
- Go 可以并发转发多个请求，适合做轻量高并发入口。

## Go 和 Python 怎么分工

在 AI 应用里，Python 通常更适合：

- 调模型。
- 做 RAG。
- 使用 AI 生态库。
- 做数据处理原型。

Go 通常更适合：

- 提供稳定 HTTP 服务入口。
- 做请求转发。
- 做并发任务调度。
- 做网关、代理、内部服务编排。

这不是绝对分工，而是这个学习项目里的推荐理解方式。

## `net/http` 是什么

`net/http` 是 Go 标准库里的 HTTP 包。

它提供：

- `http.HandleFunc` 或 `ServeMux` 注册路由。
- `http.ListenAndServe` 启动服务。
- `http.Client` 调用别的 HTTP 服务。
- `http.Request` 表示请求。
- `http.ResponseWriter` 写响应。

类比 Java：

- handler 类似 Controller 方法。
- `http.Client` 类似 RestTemplate、WebClient 或 Feign Client。
- middleware 类似 Filter。

## 什么是 JSON tag

Go 结构体字段通常是大写开头，因为大写字段才能被其他包访问。

例如：

```go
type ChatRequest struct {
    Message string `json:"message"`
}
```

`Message` 是 Go 代码里的字段名。

`json:"message"` 表示 JSON 里的字段名是：

```json
{
  "message": "hello"
}
```

如果没有 JSON tag，Go 默认会用 `Message`，这和前端常见的小写字段风格不一致。

## 为什么需要 mock 模式

学习项目必须先能运行。

如果一开始就要求：

- 必须启动 Python 服务。
- 必须配置真实模型 key。
- 必须处理后端鉴权。

那初学者很容易卡在环境问题上，而不是理解网关本身。

所以本模块默认：

```text
AI_BACKEND_MOCK=true
```

先跑通 Go 服务，再逐步接入 Python 后端。

## 什么是 goroutine

goroutine 是 Go 的轻量并发执行单元。

可以先粗略理解成“很轻的线程”。

本模块的 `/gateway/batch-chat` 会对每条消息启动一个 goroutine：

```text
消息 A -> goroutine A -> 调后端
消息 B -> goroutine B -> 调后端
消息 C -> goroutine C -> 调后端
```

这样不用等 A 完成才开始 B。

不过并发不是越多越好，所以本模块用 `MAX_BATCH_SIZE` 限制一次最多处理多少条消息。

## 学这个模块时重点看什么

先不要急着引入 Gin、微服务框架或复杂网关产品。

这一节重点看懂：

1. Go 如何启动 HTTP 服务。
2. 请求体 JSON 如何变成 struct。
3. Go 如何调用 Python HTTP 接口。
4. mock 和真实后端如何通过配置切换。
5. goroutine 如何并发处理多条任务。
6. 错误如何被隔离到单条 batch item，而不是拖垮整个请求。

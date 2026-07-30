# 流式聊天接口

这一节的目标：理解普通响应和流式响应的区别。

普通接口是：

```text
请求 -> 等模型完整生成 -> 一次性返回 JSON
```

流式接口是：

```text
请求 -> 模型生成一小段 -> 立刻返回一小段 -> 持续追加 -> 完成
```

这就是很多 AI 产品会“逐字出现”或“逐段出现”的基础。

## 先读

代码讲解：

[STREAMING_CHAT_EXPLAINED.md](STREAMING_CHAT_EXPLAINED.md)

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\09_streaming_chat
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置：

```powershell
Copy-Item .env.example .env
```

没有真实 `DEEPSEEK_API_KEY` 也可以运行，会自动使用 mock 流式输出。

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

打开浏览器演示页：

```text
http://127.0.0.1:8000/demo
```

如果端口被占用：

```powershell
python -m uvicorn main:app --reload --port 9000
```

## 测试顺序

1. `GET /health`
2. `POST /chat`
3. `GET /chat/stream`
4. `GET /chat/stream?fail_after_chunks=2`
5. `GET /demo`

## `POST /chat` 示例

普通接口会等完整答案生成后，一次性返回 JSON。

请求体：

```json
{
  "message": "请用三句话解释什么是流式输出。",
  "system_prompt": "You are a helpful assistant. Answer in Chinese."
}
```

## `GET /chat/stream` 示例

流式接口使用查询参数：

```text
http://127.0.0.1:8000/chat/stream?message=请用三句话解释什么是流式输出。
```

返回格式不是普通 JSON，而是 SSE：

```text
event: token
data: {"text": "..."}

event: done
data: {"ok": true}
```

## 模拟流式中断

为了观察流式错误处理，可以传：

```text
http://127.0.0.1:8000/chat/stream?message=hello&fail_after_chunks=2
```

它会先返回两个 `token` 事件，然后返回：

```text
event: error
data: {"message": "mock stream interrupted after configured chunks"}
```

这个练习对应真实工程里的网络中断、模型服务报错或超时。

## 用 PowerShell 观察流式输出

`/docs` 可以看到接口，但不一定能很好展示“一段段到达”的感觉。

可以用：

```powershell
curl.exe -N "http://127.0.0.1:8000/chat/stream?message=hello"
```

`-N` 的作用是关闭 curl 的缓冲，方便你看到服务端逐段返回。

## 用浏览器观察

打开：

```text
http://127.0.0.1:8000/demo
```

点击按钮后，页面会用浏览器原生 `EventSource` 连接 `/chat/stream`，并把 `token` 事件逐段追加到页面。

## 当前实现边界

本模块默认使用 mock 流式输出：

```text
完整 mock 回复 -> 切成小段 -> 每隔一小段时间 yield 一次
```

如果配置了真实 `DEEPSEEK_API_KEY`，`provider.py` 会使用 `stream=True` 调用 DeepSeek。

本模块暂时不做：

- 聊天历史保存。
- RAG sources 展示。
- 前端完整聊天 UI。
- 复杂断线重连。

这些会放到后面的模块继续组合。

## 本课练习

1. 分别调用 `POST /chat` 和 `GET /chat/stream`，说明两者返回格式有什么不同。
2. 用 `curl.exe -N` 观察 `token` 事件和 `done` 事件，解释为什么流式接口不是普通 JSON。
3. 打开 `/demo`，观察页面为什么能边接收边显示内容。
4. 把 `provider.py` 里的 mock `chunk_size` 从 `8` 改成 `3`，观察输出颗粒度变化。
5. 传 `fail_after_chunks=2`，观察流式接口已经开始返回内容后，为什么不能再依赖普通 HTTP 错误响应。
6. 故意传空 `message`，观察普通接口和流式接口是否都能返回错误。
7. 设计一个扩展：给流式输出增加 `start` 事件，返回 provider 和 model。要求说明这个事件应该在第一个 token 前还是后发送。

这些练习的重点是理解响应方式变化、SSE 格式、客户端消费方式和流式错误处理。

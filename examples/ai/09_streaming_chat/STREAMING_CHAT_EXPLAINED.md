# 流式聊天代码讲解

本模块接在普通聊天接口之后。

它不重点学习“模型怎么回答”，而是学习：

```text
服务端如何把答案逐段返回给客户端
```

## 文件职责

```text
main.py      FastAPI 接口层
provider.py  mock / DeepSeek 模型调用层
sse.py       把数据包装成 Server-Sent Events 格式
```

类比 Java：

- `main.py` 类似 Controller。
- `provider.py` 类似 Service。
- `ChatRequest` 类似请求 DTO。

## 普通响应：`POST /chat`

普通接口的流程是：

```text
客户端发送 JSON
-> FastAPI 解析成 ChatRequest
-> generate_reply()
-> 等完整 reply 生成完
-> 返回 JSON
```

代码：

```python
reply = generate_reply(
    user_message=message,
    system_prompt=payload.system_prompt,
)
```

这里的 `generate_reply()` 返回值是一个完整字符串。

所以普通接口适合短回答，但如果模型要生成很久，用户只能等待。

## 流式响应：`GET /chat/stream`

流式接口的流程是：

```text
客户端建立连接
-> 服务端 yield 第一段 token
-> 客户端立刻显示
-> 服务端继续 yield 后续 token
-> done 事件结束
```

本模块使用 FastAPI 的 `StreamingResponse`：

```python
return StreamingResponse(
    stream_sse_events(...),
    media_type="text/event-stream",
)
```

`StreamingResponse` 的关键点是：它接收一个生成器。生成器每 `yield` 一段文本，服务端就可以向客户端发送一段。

## `yield` 怎么理解

普通函数：

```python
def build_text():
    return "完整内容"
```

调用后一次性拿到完整结果。

生成器函数：

```python
def build_stream():
    yield "第一段"
    yield "第二段"
```

调用方可以一段一段拿到结果。

这就是流式输出的 Python 基础。

## SSE 格式：`sse.py`

SSE 不是随便返回字符串，而是有固定格式：

```text
event: token
data: {"text": "你好"}

```

注意最后要有空行。客户端看到空行，才知道这一条事件结束了。

本模块把这个细节封装到：

```python
format_sse(event, data)
```

这样 `main.py` 只需要关心：

```python
yield token_event(text)
yield done_event()
yield error_event(message)
```

## 为什么流式接口用 GET

浏览器原生 `EventSource` 只能直接发 GET 请求。

所以本模块的 `/chat/stream` 用查询参数接收输入：

```text
/chat/stream?message=hello
```

这和 `POST /chat` 的 JSON 请求体不一样。

后续如果要用 POST 做流式输出，可以用 `fetch()` 读取 `ReadableStream`，但那会引入更多前端代码。本模块先用最容易观察的 SSE。

## mock 流式输出

`provider.py` 里：

```python
def stream_mock_reply(...):
    for start in range(0, len(reply), chunk_size):
        time.sleep(0.12)
        yield reply[start : start + chunk_size]
```

这段代码模拟真实模型逐段输出。

- `range(0, len(reply), chunk_size)` 表示每次前进 `chunk_size` 个字符。
- `time.sleep(0.12)` 用来制造可观察的等待。
- `yield` 返回当前片段，但函数不会彻底结束。

## 真实 DeepSeek 流式输出

普通调用：

```python
stream=False
```

流式调用：

```python
stream=True
```

设置 `stream=True` 后，SDK 返回的是一个可迭代对象。每次循环能拿到一小段增量：

```python
for event in stream:
    delta = event.choices[0].delta.content
    if delta:
        yield delta
```

真实模型返回的每段大小不一定固定，它由模型服务决定。

## 错误中断

普通接口出错时，可以直接返回 HTTP 400 或 HTTP 500。

流式接口有一个特殊点：

```text
响应一旦开始，HTTP 状态码通常已经发给客户端了
```

所以本模块在流里发送：

```text
event: error
data: {"message": "..."}
```

真实项目还应该配合日志记录，不要把敏感错误直接返回给用户。

为了让这个问题可以直接观察，`/chat/stream` 提供了教学参数：

```text
fail_after_chunks=2
```

它会在返回两个 token 后模拟失败。这样你能看到一个重要差异：

```text
普通接口失败：返回 HTTP 错误
流式接口中途失败：在流里发送 error 事件
```

## `/demo` 页面

`/demo` 是一个最小浏览器演示页。

核心代码是：

```javascript
source = new EventSource(`/chat/stream?${params.toString()}`);
```

然后监听事件：

```javascript
source.addEventListener("token", ...)
source.addEventListener("done", ...)
source.addEventListener("error", ...)
```

这说明流式输出不只是后端能力，前端也必须按“逐段接收”的方式消费它。

## 本模块真正要掌握什么

学完这个模块后，应该能说清楚：

- 普通 JSON 响应和流式响应的区别。
- SSE 的基本文本格式。
- `StreamingResponse` 为什么需要生成器。
- `yield` 和 `return` 的区别。
- 浏览器 `EventSource` 如何消费 SSE。
- 为什么流式错误处理和普通接口不一样。

# 逐段讲解

这一节你只需要理解一件事：AI 应用后端通常分两层。

## `main.py`

`main.py` 是接口层。

它负责：

- 定义 `/health` 和 `/chat`
- 接收用户传来的 JSON
- 调用 `provider.py`
- 把结果返回给浏览器

你可以类比 Java Spring Boot 的 Controller。

```python
@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
```

这里的 `payload` 类似 Java 里的 `@RequestBody ChatRequest payload`。

## `ChatRequest`

```python
class ChatRequest(BaseModel):
    message: str
    system_prompt: str = "You are a helpful assistant."
```

这是请求 DTO。

请求 JSON 应该长这样：

```json
{
  "message": "你好",
  "system_prompt": "你是一个编程老师"
}
```

如果不传 `system_prompt`，就使用默认值。

## `provider.py`

`provider.py` 是模型调用层。

它负责：

- 读取 `DEEPSEEK_API_KEY`
- 没有 key 时返回 mock 回复
- 有 key 时调用真实 DeepSeek

这样设计的好处是：接口层不用关心模型调用细节。

## `.env`

`.env` 是本地配置文件。

可以类比 Java 项目里的：

- `application.properties`
- `application.yml`

示例：

```text
DEEPSEEK_API_KEY=你的 deepseek key
DEEPSEEK_MODEL=deepseek-v4-flash
```

## `mock` 是什么

`mock` 就是假实现。

它不调用真实 AI，只返回固定格式的假数据。

初学阶段很有用，因为你可以先确认接口流程是通的，再处理 API Key、网络、计费、模型参数这些问题。

## 你现在要看懂的调用链

```text
浏览器 /docs
-> POST /chat
-> main.py 的 chat()
-> provider.py 的 generate_reply()
-> mock 或 deepseek
-> 返回 reply
```

如果这条链路你能说清楚，这一节就算过。

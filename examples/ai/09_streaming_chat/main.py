from collections.abc import Iterator
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from provider import generate_reply, get_api_key, get_model_name, get_provider_name, stream_reply
from sse import done_event, error_event, token_event, start_event

app = FastAPI(title="Streaming Chat")


class ChatRequest(BaseModel):
    # 请求 DTO：客户端用 JSON 调普通聊天接口时，会传 message 和 system_prompt。
    # 类比 Java 里的 ChatRequest DTO，不是数据库表。
    message: str
    system_prompt: str = "You are a helpful assistant."


def validate_message(message: str) -> str:
    # 把校验抽出来，是为了让普通接口和流式接口走同一套规则。
    # 这样不会出现 /chat 接受空消息，但 /chat/stream 又拒绝空消息的混乱行为。
    cleaned_message = message.strip()
    if not cleaned_message:
        raise HTTPException(status_code=400, detail="message must not be empty")
    return cleaned_message


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
        "has_api_key": bool(get_api_key()),
        "stream_protocol": "server-sent events",
    }


@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
    # 普通响应接口：
    # 客户端发一个 JSON 请求，服务端等完整答案生成完，再返回一个 JSON。
    # 缺点是答案很长时，用户要一直等到最后才看到内容。
    message = validate_message(payload.message)
    reply = generate_reply(
        user_message=message,
        system_prompt=payload.system_prompt,
    )
    return {
        "message": message,
        "reply": reply,
        "provider": get_provider_name(),
        "model": get_model_name(),
    }


def stream_sse_events(
    message: str,
    system_prompt: str,
    fail_after_chunks: int | None = None,
) -> Iterator[str]:
    # 这个生成器负责把模型增量文本包装成 SSE 事件。
    # StreamingResponse 会不断消费这个生成器，每 yield 一次，就向客户端发送一段。
    try:
        yield start_event()
        for chunk_index, text in enumerate(
            stream_reply(user_message=message, system_prompt=system_prompt),
            start=1,
        ):
            # fail_after_chunks 是教学用参数，用来模拟“模型流式输出到一半失败”。
            # 真实项目里可能是网络中断、模型服务报错、超时等原因。
            if fail_after_chunks is not None and chunk_index > fail_after_chunks:
                raise RuntimeError("mock stream interrupted after configured chunks")
            yield token_event(text)
        yield done_event()
    except Exception as error:
        # 教学模块里先把错误信息返回到流里，方便观察中断。
        # 真实项目要进一步记录日志，并避免把敏感错误细节直接暴露给用户。
        yield error_event(str(error))


@app.get("/chat/stream")
def chat_stream(
    message: str = Query(...),
    system_prompt: str = Query("You are a helpful assistant."),
    fail_after_chunks: int | None = Query(None),
) -> StreamingResponse:
    # SSE 通常用 GET，因为浏览器原生 EventSource 只能直接发 GET。
    # message 和 system_prompt 都来自查询参数，例如：
    # /chat/stream?message=hello&system_prompt=You%20are%20helpful
    cleaned_message = validate_message(unquote(message))
    if fail_after_chunks is not None and fail_after_chunks < 0:
        raise HTTPException(status_code=400, detail="fail_after_chunks must be greater than or equal to 0")

    headers = {
        # 关闭代理或浏览器的缓冲倾向，让客户端更容易尽快看到每个事件。
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        stream_sse_events(
            message=cleaned_message,
            system_prompt=system_prompt,
            fail_after_chunks=fail_after_chunks,
        ),
        media_type="text/event-stream",
        headers=headers,
    )


@app.get("/demo", response_class=HTMLResponse)
def demo_page() -> str:
    # 这个页面是学习用的最小前端，方便直接在浏览器里观察流式输出。
    # 它不引入前端框架，因为本模块目标是理解 SSE，不是学习复杂前端工程。
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Streaming Chat Demo</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; line-height: 1.6; }
    main { max-width: 840px; margin: 0 auto; }
    textarea { width: 100%; min-height: 96px; box-sizing: border-box; padding: 12px; font: inherit; }
    button { margin-top: 12px; padding: 8px 14px; font: inherit; cursor: pointer; }
    pre { min-height: 180px; white-space: pre-wrap; border: 1px solid #ccc; padding: 12px; background: #fafafa; }
    .meta { color: #666; font-size: 14px; }
  </style>
</head>
<body>
  <main>
    <h1>Streaming Chat Demo</h1>
    <textarea id="message">请用三句话解释什么是流式输出。</textarea>
    <br />
    <button id="send">发送</button>
    <p class="meta" id="status">未连接</p>
    <pre id="output"></pre>
  </main>
  <script>
    const sendButton = document.getElementById("send");
    const messageInput = document.getElementById("message");
    const output = document.getElementById("output");
    const statusText = document.getElementById("status");
    let source = null;

    sendButton.addEventListener("click", () => {
      if (source) {
        source.close();
      }
      output.textContent = "";
      statusText.textContent = "连接中";

      const params = new URLSearchParams({
        message: messageInput.value,
        system_prompt: "You are a helpful assistant. Answer in Chinese."
      });
      source = new EventSource(`/chat/stream?${params.toString()}`);

      source.addEventListener("token", (event) => {
        const payload = JSON.parse(event.data);
        output.textContent += payload.text;
      });

      source.addEventListener("done", () => {
        statusText.textContent = "完成";
        source.close();
      });

      source.addEventListener("error", (event) => {
        statusText.textContent = "连接中断或服务返回错误";
        if (event.data) {
          const payload = JSON.parse(event.data);
          output.textContent += `\\n[error] ${payload.message}`;
        }
        source.close();
      });
    });
  </script>
</body>
</html>
"""

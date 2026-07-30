import json
from provider import generate_reply, get_api_key, get_model_name, get_provider_name, stream_reply

def format_sse(event: str, data: dict) -> str:
    # SSE 的全称是 Server-Sent Events。
    # 浏览器或客户端收到的每一段数据，都需要按固定文本格式发送：
    #
    # event: 事件名
    # data: JSON 字符串
    #
    # 中间和结尾的空行不能省略，否则客户端不知道一条事件已经结束。
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def start_event() -> str:
    # start 事件告诉前端：这次流式输出开始了。
    return format_sse("start", {"provider" : get_provider_name(),
                                "model" : get_model_name()})

def token_event(text: str) -> str:
    # token 事件表示“模型又吐出了一小段文本”。
    # 这里的 token 不一定是模型底层 tokenizer 的 token，也可以理解成一小段增量内容。
    return format_sse("token", {"text": text})


def done_event() -> str:
    # done 事件告诉前端：这次流式输出结束了。
    return format_sse("done", {"ok": True})


def error_event(message: str) -> str:
    # error 事件用于把流式过程中发生的错误也用 SSE 格式返回。
    # 普通接口可以直接抛 HTTPException；但流式响应开始后，HTTP 状态码通常已经发出去了，
    # 所以更适合在流里发送一个 error 事件。
    return format_sse("error", {"message": message})

import os

from fastapi import FastAPI
from pydantic import BaseModel

from provider import generate_reply, get_api_key, get_model_name, get_provider_name

# main.py 负责 Web API 层。
# 它只处理 HTTP 请求和响应，不直接写模型调用细节。
app = FastAPI(title="Minimal DeepSeek Chat API")


class ChatRequest(BaseModel):
    # message 是用户真正输入的问题。
    message: str
    # system_prompt 用来告诉模型应该用什么身份和风格回答。
    system_prompt: str = "You are a helpful assistant."


@app.get("/health")
def health() -> dict:
    # 这个接口用来确认服务是否启动成功，以及当前使用 mock 还是真实 DeepSeek。
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
        "has_api_key": bool(get_api_key()),
    }


@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
    # payload 来自请求体 JSON。
    # provider.py 会决定使用 mock 回复，还是调用真实 DeepSeek。
    reply = generate_reply(
        user_message=payload.message,
        system_prompt=payload.system_prompt,
    )
    return {
        "message": payload.message,
        "reply": reply,
        "provider": get_provider_name(),
        "model": get_model_name(),
    }

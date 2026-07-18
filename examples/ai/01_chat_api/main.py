import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from provider import generate_reply

# API 层负责接收请求、做基础校验，再把生成逻辑交给 provider。
app = FastAPI(title="Minimal AI Chat API")


class ChatRequest(BaseModel):
    # system_prompt 先给默认值，方便你直接测试接口。
    message: str
    system_prompt: str = "You are a helpful assistant."


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": "openai"}


@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
    # 把密钥检查放在入口层，避免 provider 在缺少配置时才报错。
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    reply = generate_reply(
        user_message=payload.message,
        system_prompt=payload.system_prompt,
    )
    return {"reply": reply}

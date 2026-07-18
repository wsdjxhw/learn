from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from db import (
    add_message,
    create_session,
    get_session,
    init_db,
    list_messages,
    list_messages_for_model,
    list_sessions,
)
from provider import generate_reply, get_model_name, get_provider_name

app = FastAPI(title="AI Chat With History")


class SessionCreate(BaseModel):
    # 类比 Java 里的请求 DTO：创建会话时，客户端只需要传 title。
    title: str


class ChatRequest(BaseModel):
    # 用户在某个会话里发送的一条消息。
    message: str
    # system_prompt 不直接保存到数据库，只临时放到模型上下文最前面。
    system_prompt: str = "You are a helpful assistant."


@app.on_event("startup")
def startup() -> None:
    # 服务启动时初始化数据库表。
    init_db()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
    }


@app.post("/sessions")
def create_chat_session(payload: SessionCreate) -> dict:
    # 创建一个新的聊天会话。
    return create_session(title=payload.title)


@app.get("/sessions")
def get_chat_sessions() -> dict:
    # 查看所有会话。
    return {"items": list_sessions()}


@app.get("/sessions/{session_id}/messages")
def get_chat_messages(session_id: int) -> dict:
    # 查看某个会话里的历史消息。
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"items": list_messages(session_id)}


@app.post("/sessions/{session_id}/chat")
def chat(session_id: int, payload: ChatRequest) -> dict:
    # 1. 先确认会话存在。
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. 保存用户消息。
    user_message = add_message(
        session_id=session_id,
        role="user",
        content=payload.message,
    )

    # 3. 取出历史消息，拼上 system_prompt，交给模型。
    model_messages = [
        {"role": "system", "content": payload.system_prompt},
        *list_messages_for_model(session_id),
    ]
    reply_text = generate_reply(model_messages)

    # 4. 保存助手回复。
    assistant_message = add_message(
        session_id=session_id,
        role="assistant",
        content=reply_text,
    )

    return {
        "session_id": session_id,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "provider": get_provider_name(),
        "model": get_model_name(),
    }

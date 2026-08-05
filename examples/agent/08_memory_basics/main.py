from typing import Any

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from database import get_db, init_db
from memory_extractor import extract_memory_candidates
from memory_store import (
    add_message,
    count_messages,
    list_memories,
    search_memories,
    to_memory_response,
    upsert_memories,
)
from provider import generate_agent_answer
from schemas import ChatRequest, ChatResponse, MemoryExtractRequest, MemorySearchRequest
from settings import get_settings


# main.py 是 Web API 层。
# Java 类比：可以理解成 Controller，只接收请求、调用业务函数、返回 DTO。
app = FastAPI(title="Agent Memory Basics Teaching Demo")


@app.on_event("startup")
def on_startup() -> None:
    # 服务启动时创建数据库表。
    # 本模块关注长期记忆基础，不先引入 Alembic，避免初学者卡在迁移工具上。
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "module": "08_memory_basics",
        "model_mode": settings.model_mode,
        "database_url": settings.database_url,
        "has_deepseek_api_key": bool(settings.deepseek_api_key),
    }


@app.post("/memory/extract")
def preview_memory_extract(payload: MemoryExtractRequest) -> dict[str, Any]:
    # payload 来自请求体。
    # 这个接口只做提取预览，不写数据库，适合先理解“哪些话会变成记忆”。
    candidates = extract_memory_candidates(payload.text)
    return {"candidates": [candidate.model_dump() for candidate in candidates]}


@app.get("/users/{user_id}/memories")
def get_user_memories(user_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    # user_id 是路径参数，来自 /users/{user_id}/memories。
    # 长期记忆必须按用户隔离，否则 A 用户的偏好可能影响 B 用户的回答。
    return {"memories": [memory.model_dump() for memory in list_memories(db, user_id)]}


@app.post("/memory/search")
def search_user_memories(payload: MemorySearchRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    # 搜索接口帮助你单独验证“当前问题 -> 相关长期记忆”的匹配结果。
    memories = search_memories(db, payload.user_id, payload.query, payload.limit)
    return {"memories": [to_memory_response(memory).model_dump() for memory in memories]}


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    # 这条接口把长期记忆的完整链路串起来：
    # 1. 保存 user 原始消息到聊天历史。
    # 2. 从 user 消息提取候选记忆。
    # 3. 把候选记忆 upsert 到长期记忆表。
    # 4. 按当前问题检索相关记忆。
    # 5. 把相关记忆交给模型生成回答。
    # 6. 保存 assistant 原始回复到聊天历史。
    add_message(db, payload.user_id, "user", payload.message)

    extracted = extract_memory_candidates(payload.message)
    saved = upsert_memories(db, payload.user_id, extracted)

    # 先保存再检索，用户本轮刚表达的偏好也可以立刻影响本轮回答。
    related_memories = search_memories(db, payload.user_id, payload.message, limit=5)
    answer = generate_agent_answer(payload.message, related_memories)
    add_message(db, payload.user_id, "assistant", answer)

    return ChatResponse(
        answer=answer,
        user_id=payload.user_id,
        used_memories=[to_memory_response(memory) for memory in related_memories],
        extracted_memories=extracted,
        saved_memory_count=len(saved),
        message_count=count_messages(db, payload.user_id),
    )

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, init_db
from memory_extractor import extract_memory_candidates
from memory_safety import screen_memory_candidates
from memory_store import (
    add_message,
    count_messages,
    expire_due_memories,
    get_memory_for_user,
    list_memories,
    record_rejections,
    search_memories,
    soft_delete_memory,
    to_memory_response,
    update_memory,
    upsert_memories,
)
from provider import generate_agent_answer
from schemas import (
    ChatRequest,
    ChatResponse,
    ExpireScanResponse,
    ExtractPreviewResponse,
    MemoryDeleteRequest,
    MemoryExtractRequest,
    MemorySearchRequest,
    MemoryUpdateRequest,
)
from settings import get_settings


# main.py 是 Web API 层。
# Java 类比：可以理解成 Controller，只负责接收请求、调用业务函数、返回 DTO。
app = FastAPI(title="Agent Memory Governance Teaching Demo")


@app.on_event("startup")
def on_startup() -> None:
    # 服务启动时创建数据库表。
    # 生产项目会使用 Alembic；教学模块先用 create_all 保证开箱可跑。
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "module": "09_memory_governance",
        "model_mode": settings.model_mode,
        "database_url": settings.database_url,
        "has_deepseek_api_key": bool(settings.deepseek_api_key),
    }


@app.post("/memory/extract", response_model=ExtractPreviewResponse)
def preview_memory_extract(payload: MemoryExtractRequest) -> ExtractPreviewResponse:
    # 这个接口只预览治理结果，不写数据库。
    # 它能让学习者看到：同一句话里哪些信息可以记，哪些因为敏感而被拒绝。
    candidates = extract_memory_candidates(payload.text)
    accepted, rejected = screen_memory_candidates(candidates)
    return ExtractPreviewResponse(accepted=accepted, rejected=rejected)


@app.get("/users/{user_id}/memories")
def get_user_memories(
    user_id: str,
    include_deleted: bool = Query(default=False),
    include_expired: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # include_deleted / include_expired 是查询参数。
    # 默认不返回 deleted 和 expired，因为它们不应该影响 Agent 回答。
    memories = list_memories(db, user_id, include_deleted=include_deleted, include_expired=include_expired)
    return {"memories": [memory.model_dump() for memory in memories]}


@app.post("/memory/search")
def search_user_memories(payload: MemorySearchRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    # search_memories 内部会过滤 deleted 和 expired。
    # 这能验证删除或过期后的记忆不会再进入模型上下文。
    memories = search_memories(db, payload.user_id, payload.query, payload.limit)
    return {"memories": [to_memory_response(memory).model_dump() for memory in memories]}


@app.patch("/users/{user_id}/memories/{memory_id}")
def patch_user_memory(
    user_id: str,
    memory_id: str,
    payload: MemoryUpdateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # PATCH 表示局部更新。
    # 例如只改 value，不需要提交整条 memory 的所有字段。
    memory = get_memory_for_user(db, user_id, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory_id 不存在，或不属于当前 user_id。")
    updated = update_memory(db, memory, payload)
    return {"memory": to_memory_response(updated).model_dump()}


@app.delete("/users/{user_id}/memories/{memory_id}")
def delete_user_memory(
    user_id: str,
    memory_id: str,
    payload: MemoryDeleteRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # DELETE 接口这里做软删除。
    # 对用户体验来说它已经“不可用”；对审计来说记录还在。
    memory = get_memory_for_user(db, user_id, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="memory_id 不存在，或不属于当前 user_id。")
    deleted = soft_delete_memory(db, memory, payload)
    return {"memory": to_memory_response(deleted).model_dump()}


@app.post("/memory/expire-scan", response_model=ExpireScanResponse)
def scan_expired_memories(db: Session = Depends(get_db)) -> ExpireScanResponse:
    # 这个接口模拟定时任务。
    # 它会把 expires_at 已到期的 active 记忆标记成 expired。
    expired = expire_due_memories(db)
    return ExpireScanResponse(expired_count=len(expired), expired_memory_ids=[memory.memory_id for memory in expired])


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    # 完整链路：
    # 1. 保存原始 user message。
    # 2. 提取候选记忆。
    # 3. 敏感信息过滤，拒绝高风险记忆。
    # 4. 只保存通过治理的候选记忆。
    # 5. 检索 active 且未过期的相关记忆。
    # 6. 用过滤后的记忆生成回答。
    # 7. 保存 assistant message。
    add_message(db, payload.user_id, "user", payload.message)

    candidates = extract_memory_candidates(payload.message)
    accepted, rejected = screen_memory_candidates(candidates)
    saved = upsert_memories(db, payload.user_id, accepted)
    record_rejections(db, payload.user_id, [item.model_dump() for item in rejected])

    related_memories = search_memories(db, payload.user_id, payload.message, limit=5)
    answer = generate_agent_answer(payload.message, related_memories)
    add_message(db, payload.user_id, "assistant", answer)

    return ChatResponse(
        answer=answer,
        user_id=payload.user_id,
        used_memories=[to_memory_response(memory) for memory in related_memories],
        extracted_memories=accepted,
        rejected_memories=rejected,
        saved_memory_count=len(saved),
        message_count=count_messages(db, payload.user_id),
    )

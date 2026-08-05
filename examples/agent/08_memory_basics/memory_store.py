from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ConversationMessage, MemoryUseLog, UserMemory
from schemas import MemoryCandidate, MemoryResponse


def add_message(db: Session, user_id: str, role: str, content: str) -> ConversationMessage:
    # 聊天历史保存原始消息，role 常见值是 user / assistant。
    # 它回答的是“当时说了什么”，不回答“以后应该复用什么”。
    message = ConversationMessage(user_id=user_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def count_messages(db: Session, user_id: str) -> int:
    # count_messages 用于接口返回，帮助学习者看到聊天历史在增长。
    # 这里用查询后 len()，语法更直观；生产大表应使用 SQL count()。
    messages = db.execute(select(ConversationMessage).where(ConversationMessage.user_id == user_id)).scalars().all()
    return len(messages)


def upsert_memories(db: Session, user_id: str, candidates: list[MemoryCandidate]) -> list[UserMemory]:
    # upsert 表示“有就更新，没有就插入”。
    # 长期记忆很少应该无限追加；同一个 key 的新表达通常是在修正旧记忆。
    saved: list[UserMemory] = []
    now = datetime.utcnow()

    for candidate in candidates:
        existing = (
            db.execute(
                select(UserMemory).where(
                    UserMemory.user_id == user_id,
                    UserMemory.memory_type == candidate.memory_type,
                    UserMemory.key == candidate.key,
                )
            )
            .scalars()
            .first()
        )

        if existing:
            existing.value = candidate.value
            existing.source_text = candidate.source_text
            existing.confidence = candidate.confidence
            existing.updated_at = now
            db.add(existing)
            saved.append(existing)
            continue

        memory = UserMemory(
            memory_id=str(uuid4()),
            user_id=user_id,
            memory_type=candidate.memory_type,
            key=candidate.key,
            value=candidate.value,
            source_text=candidate.source_text,
            confidence=candidate.confidence,
            created_at=now,
            updated_at=now,
        )
        db.add(memory)
        saved.append(memory)

    db.commit()
    for memory in saved:
        db.refresh(memory)
    return saved


def list_memories(db: Session, user_id: str) -> list[MemoryResponse]:
    memories = (
        db.execute(
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .order_by(UserMemory.memory_type.asc(), UserMemory.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return [to_memory_response(memory) for memory in memories]


def search_memories(db: Session, user_id: str, query: str, limit: int = 5) -> list[UserMemory]:
    # 这是教学版检索：先按 user_id 隔离，再用简单打分找相关记忆。
    # 真实项目会用 embedding、关键词索引或混合检索；但边界仍然一样：只能检索当前用户的记忆。
    memories = db.execute(select(UserMemory).where(UserMemory.user_id == user_id)).scalars().all()
    scored: list[tuple[int, UserMemory]] = []
    for memory in memories:
        score = _score_memory(memory, query)
        if score > 0:
            scored.append((score, memory))

    scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
    result = [memory for _, memory in scored[:limit]]

    if result:
        now = datetime.utcnow()
        for memory in result:
            memory.last_used_at = now
            db.add(memory)
            db.add(MemoryUseLog(user_id=user_id, query=query, memory_id=memory.memory_id, created_at=now))
        db.commit()
        for memory in result:
            db.refresh(memory)

    return result


def _score_memory(memory: UserMemory, query: str) -> int:
    query_lower = query.lower()
    key_lower = memory.key.lower()
    value_lower = memory.value.lower()

    score = 0
    if memory.memory_type == "instruction":
        # instruction 类记忆通常应该默认带入，例如回复语言、回答风格。
        score += 3
    if memory.memory_type == "profile" and any(word in query for word in ("我", "我的", "适合", "学习", "规划")):
        score += 2
    if memory.memory_type == "preference" and any(word in query for word in ("推荐", "选择", "学习", "方案", "内容")):
        score += 2
    if key_lower in query_lower or value_lower in query_lower:
        score += 4
    return score


def to_memory_response(memory: UserMemory) -> MemoryResponse:
    # ORM 对象不要直接暴露给前端。
    # 转 DTO 可以控制字段命名、时间格式，也能避免后续表字段变化影响接口。
    return MemoryResponse(
        memory_id=memory.memory_id,
        user_id=memory.user_id,
        memory_type=memory.memory_type,
        key=memory.key,
        value=memory.value,
        source_text=memory.source_text,
        confidence=memory.confidence,
        created_at=memory.created_at.isoformat(),
        updated_at=memory.updated_at.isoformat(),
        last_used_at=memory.last_used_at.isoformat() if memory.last_used_at else None,
    )

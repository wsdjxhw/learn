import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ConversationMessage, MemoryAuditLog, UserMemory
from schemas import MemoryCandidate, MemoryDeleteRequest, MemoryResponse, MemoryUpdateRequest
from uuid import uuid4


def add_message(db: Session, user_id: str, role: str, content: str) -> ConversationMessage:
    # 聊天历史保存原始 user / assistant 消息。
    # 它不等于长期记忆，所以不受记忆删除接口影响。
    message = ConversationMessage(user_id=user_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def count_messages(db: Session, user_id: str) -> int:
    messages = db.execute(select(ConversationMessage).where(ConversationMessage.user_id == user_id)).scalars().all()
    return len(messages)


def upsert_memories(db: Session, user_id: str, candidates: list[MemoryCandidate]) -> list[UserMemory]:
    # upsert 表示“有就更新，没有就插入”。
    # 治理模块里，如果旧记忆已经 deleted，再次提取到同一个 key，会重新激活它。
    saved: list[UserMemory] = []
    now = datetime.utcnow()

    for candidate in candidates:
        expires_at = _calculate_expires_at(candidate.retention_days, now)
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
            before = _memory_snapshot(existing)
            existing.value = candidate.value
            existing.source_text = candidate.source_text
            existing.confidence = candidate.confidence
            existing.status = "active"
            existing.expires_at = expires_at
            existing.deleted_at = None
            existing.delete_reason = None
            existing.updated_at = now
            db.add(existing)
            _add_audit_log(db, user_id, existing.memory_id, "updated", "从用户消息重新提取并更新记忆。", before, _memory_snapshot(existing))
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
            status="active",
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        db.add(memory)
        _add_audit_log(db, user_id, memory.memory_id, "created", "从用户消息提取并创建记忆。", {}, _memory_snapshot(memory))
        saved.append(memory)

    db.commit()
    for memory in saved:
        db.refresh(memory)
    return saved


def list_memories(
    db: Session,
    user_id: str,
    include_deleted: bool = False,
    include_expired: bool = False,
) -> list[MemoryResponse]:
    memories = db.execute(select(UserMemory).where(UserMemory.user_id == user_id)).scalars().all()
    result: list[MemoryResponse] = []
    for memory in memories:
        if not include_deleted and memory.status == "deleted":
            continue
        if not include_expired and is_memory_expired(memory):
            continue
        result.append(to_memory_response(memory))
    result.sort(key=lambda item: item.updated_at, reverse=True)
    return result


def get_memory_for_user(db: Session, user_id: str, memory_id: str) -> UserMemory | None:
    return (
        db.execute(select(UserMemory).where(UserMemory.user_id == user_id, UserMemory.memory_id == memory_id))
        .scalars()
        .first()
    )


def search_memories(db: Session, user_id: str, query: str, limit: int = 5) -> list[UserMemory]:
    # 检索必须同时排除 deleted 和 expired。
    # 否则用户删掉的记忆、已经过期的旧偏好仍然会影响回答。
    memories = db.execute(select(UserMemory).where(UserMemory.user_id == user_id, UserMemory.status == "active")).scalars().all()
    scored: list[tuple[int, UserMemory]] = []
    for memory in memories:
        if is_memory_expired(memory):
            continue
        score = _score_memory(memory, query)
        if score > 0:
            scored.append((score, memory))

    scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
    result = [memory for _, memory in scored[:limit]]

    if result:
        now = datetime.utcnow()
        for memory in result:
            before = _memory_snapshot(memory)
            memory.last_used_at = now
            db.add(memory)
            _add_audit_log(db, user_id, memory.memory_id, "used", f"回答问题时检索到该记忆：{query}", before, _memory_snapshot(memory))
        db.commit()
        for memory in result:
            db.refresh(memory)

    return result


def update_memory(db: Session, memory: UserMemory, payload: MemoryUpdateRequest) -> UserMemory:
    # 手动更新用于修正错误记忆。
    # 真实产品通常会在“记忆管理页面”提供类似能力。
    before = _memory_snapshot(memory)
    if payload.value is not None:
        memory.value = payload.value
    if payload.confidence is not None:
        memory.confidence = payload.confidence
    if payload.clear_expiration:
        memory.expires_at = None
    elif payload.expires_in_days is not None:
        memory.expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)

    memory.status = "active"
    memory.deleted_at = None
    memory.delete_reason = None
    memory.updated_at = datetime.utcnow()
    db.add(memory)
    _add_audit_log(db, memory.user_id, memory.memory_id, "updated", payload.reason, before, _memory_snapshot(memory))
    db.commit()
    db.refresh(memory)
    return memory


def soft_delete_memory(db: Session, memory: UserMemory, payload: MemoryDeleteRequest) -> UserMemory:
    # 这里使用软删除：把 status 改成 deleted，而不是直接 Remove。
    # 软删除能保留审计现场；生产系统也可以在合规要求下做真正物理删除。
    before = _memory_snapshot(memory)
    now = datetime.utcnow()
    memory.status = "deleted"
    memory.deleted_at = now
    memory.delete_reason = payload.reason
    memory.updated_at = now
    db.add(memory)
    _add_audit_log(db, memory.user_id, memory.memory_id, "deleted", payload.reason, before, _memory_snapshot(memory))
    db.commit()
    db.refresh(memory)
    return memory


def expire_due_memories(db: Session) -> list[UserMemory]:
    # 教学版过期扫描。
    # 真实项目通常由定时任务定期执行，而不是靠用户手动调用接口。
    now = datetime.utcnow()
    memories = (
        db.execute(
            select(UserMemory).where(
                UserMemory.status == "active",
                UserMemory.expires_at.is_not(None),
                UserMemory.expires_at <= now,
            )
        )
        .scalars()
        .all()
    )
    for memory in memories:
        before = _memory_snapshot(memory)
        memory.status = "expired"
        memory.updated_at = now
        db.add(memory)
        _add_audit_log(db, memory.user_id, memory.memory_id, "expired", "记忆达到 expires_at，过期扫描将其标记为 expired。", before, _memory_snapshot(memory))
    db.commit()
    for memory in memories:
        db.refresh(memory)
    return memories


def record_rejections(db: Session, user_id: str, rejected_items: list[dict]) -> None:
    # 被拒绝的内容不进入 user_memories，但可以记录一条不含敏感值细节的审计说明。
    # 这里为了教学可见，reason 会保留；生产系统要进一步避免日志泄露原始敏感内容。
    for item in rejected_items:
        _add_audit_log(
            db,
            user_id=user_id,
            memory_id=None,
            action="rejected",
            reason=item["reason"],
            before={},
            after={"risk_type": item["risk_type"]},
        )
    db.commit()


def is_memory_expired(memory: UserMemory) -> bool:
    return memory.expires_at is not None and memory.expires_at <= datetime.utcnow()


def to_memory_response(memory: UserMemory) -> MemoryResponse:
    status = memory.status
    expired = is_memory_expired(memory)
    if status == "active" and expired:
        status = "expired"
    return MemoryResponse(
        memory_id=memory.memory_id,
        user_id=memory.user_id,
        memory_type=memory.memory_type,
        key=memory.key,
        value=memory.value,
        source_text=memory.source_text,
        confidence=memory.confidence,
        status=status,
        created_at=memory.created_at.isoformat(),
        updated_at=memory.updated_at.isoformat(),
        last_used_at=memory.last_used_at.isoformat() if memory.last_used_at else None,
        expires_at=memory.expires_at.isoformat() if memory.expires_at else None,
        deleted_at=memory.deleted_at.isoformat() if memory.deleted_at else None,
        delete_reason=memory.delete_reason,
        is_expired=expired,
    )


def _calculate_expires_at(retention_days: int | None, now: datetime) -> datetime | None:
    if retention_days is None:
        return None
    return now + timedelta(days=retention_days)


def _score_memory(memory: UserMemory, query: str) -> int:
    query_lower = query.lower()
    key_lower = memory.key.lower()
    value_lower = memory.value.lower()

    score = 0
    if memory.memory_type == "instruction":
        score += 3
    if memory.memory_type == "profile" and any(word in query for word in ("我", "我的", "适合", "学习", "规划")):
        score += 2
    if memory.memory_type == "preference" and any(word in query for word in ("推荐", "选择", "学习", "方案", "内容")):
        score += 2
    if key_lower in query_lower or value_lower in query_lower:
        score += 4
    return score


def _memory_snapshot(memory: UserMemory) -> dict:
    # snapshot 用于审计日志。
    # before_json / after_json 能帮助排查记忆是什么时候、因为什么发生变化。
    return {
        "memory_id": memory.memory_id,
        "user_id": memory.user_id,
        "memory_type": memory.memory_type,
        "key": memory.key,
        "value": memory.value,
        "confidence": memory.confidence,
        "status": memory.status,
        "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
        "deleted_at": memory.deleted_at.isoformat() if memory.deleted_at else None,
    }


def _add_audit_log(
    db: Session,
    user_id: str,
    memory_id: str | None,
    action: str,
    reason: str,
    before: dict,
    after: dict,
) -> None:
    log = MemoryAuditLog(
        user_id=user_id,
        memory_id=memory_id,
        action=action,
        reason=reason,
        before_json=json.dumps(before, ensure_ascii=False),
        after_json=json.dumps(after, ensure_ascii=False),
    )
    db.add(log)

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ConversationMessage(Base):
    # ConversationMessage 保存原始聊天历史。
    # 它的职责是“还原对话发生了什么”，不是给 Agent 长期复用。
    # Java 类比：这是聊天消息 Entity，和下面的 UserMemory 是两种不同表。
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UserMemory(Base):
    # UserMemory 保存长期记忆。
    # 长期记忆不是原文堆积，而是从对话里筛选、压缩、结构化后的信息。
    __tablename__ = "user_memories"
    __table_args__ = (
        # 同一个用户的同一种 key 只保留一条，重复表达时更新旧记忆。
        # 例如用户多次说“请用中文回答”，应该更新 language 记忆，而不是插入很多重复行。
        UniqueConstraint("user_id", "memory_type", "key", name="uq_user_memory_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    memory_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MemoryUseLog(Base):
    # MemoryUseLog 记录哪次问题使用了哪些记忆。
    # 这不是记忆本身，而是审计线索：以后排查“为什么 Agent 这样回答”会用到。
    __tablename__ = "memory_use_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    memory_id: Mapped[str] = mapped_column(ForeignKey("user_memories.memory_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    memory: Mapped[UserMemory] = relationship()

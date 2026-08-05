from typing import Literal

from pydantic import BaseModel, Field


MemoryType = Literal["preference", "profile", "instruction"]
MemoryStatus = Literal["active", "expired", "deleted"]


class ChatRequest(BaseModel):
    # ChatRequest 是 /agent/chat 的请求体 DTO。
    # user_id 用来隔离不同用户的记忆，message 是本轮用户输入。
    user_id: str = Field(min_length=1, description="用户标识。长期记忆必须按用户隔离。")
    message: str = Field(min_length=1, description="用户本轮输入。")


class MemoryExtractRequest(BaseModel):
    # 只预览提取和治理判断，不写数据库。
    text: str = Field(min_length=1, description="需要分析的一段用户输入。")


class MemorySearchRequest(BaseModel):
    user_id: str = Field(min_length=1, description="要检索哪个用户的记忆。")
    query: str = Field(min_length=1, description="当前问题，用它匹配相关长期记忆。")
    limit: int = Field(default=5, ge=1, le=20, description="最多返回几条记忆。")


class MemoryCandidate(BaseModel):
    # MemoryCandidate 是候选记忆。
    # retention_days 表示建议保存多久，None 表示暂不过期。
    memory_type: MemoryType
    key: str
    value: str
    source_text: str
    confidence: float = Field(ge=0, le=1)
    reason: str
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class MemoryRejection(BaseModel):
    # MemoryRejection 表示某段信息被拒绝写入长期记忆。
    # 拒绝也要结构化返回，这样前端和日志才能解释清楚。
    source_text: str
    risk_type: str
    reason: str


class MemoryResponse(BaseModel):
    memory_id: str
    user_id: str
    memory_type: str
    key: str
    value: str
    source_text: str
    confidence: float
    status: MemoryStatus
    created_at: str
    updated_at: str
    last_used_at: str | None
    expires_at: str | None
    deleted_at: str | None
    delete_reason: str | None
    is_expired: bool


class MemoryUpdateRequest(BaseModel):
    # 用户或后台管理流程可以修正长期记忆。
    # value 是新的记忆值；expires_in_days 用于重新设置过期时间。
    value: str | None = Field(default=None, min_length=1, description="新的记忆值。不传表示不改 value。")
    confidence: float | None = Field(default=None, ge=0, le=1, description="新的置信度。不传表示不改。")
    expires_in_days: int | None = Field(default=None, ge=1, le=3650, description="从现在开始几天后过期。")
    clear_expiration: bool = Field(default=False, description="是否清空过期时间。")
    reason: str = Field(min_length=1, description="为什么要更新这条记忆。")


class MemoryDeleteRequest(BaseModel):
    # 删除记忆必须带原因。
    # 真实系统里这能帮助审计：用户主动删除、系统误提取、还是合规要求删除。
    reason: str = Field(default="用户请求删除长期记忆", min_length=1)


class ChatResponse(BaseModel):
    answer: str
    user_id: str
    used_memories: list[MemoryResponse]
    extracted_memories: list[MemoryCandidate]
    rejected_memories: list[MemoryRejection]
    saved_memory_count: int
    message_count: int


class ExtractPreviewResponse(BaseModel):
    accepted: list[MemoryCandidate]
    rejected: list[MemoryRejection]


class ExpireScanResponse(BaseModel):
    expired_count: int
    expired_memory_ids: list[str]

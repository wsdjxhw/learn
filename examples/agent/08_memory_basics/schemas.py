from typing import Literal

from pydantic import BaseModel, Field


MemoryType = Literal["preference", "profile", "instruction"]


class ChatRequest(BaseModel):
    # ChatRequest 是 /agent/chat 的请求体 DTO。
    # Java 类比：BaseModel 类似 Controller 入参 DTO，不是数据库 Entity。
    user_id: str = Field(min_length=1, description="用户标识。长期记忆必须按用户隔离。")
    message: str = Field(min_length=1, description="用户本轮输入。")


class MemoryExtractRequest(BaseModel):
    # 这个 DTO 用于只预览提取结果，不写数据库。
    # 它帮助初学者单独观察“原始文本 -> 记忆候选”的转换。
    text: str = Field(min_length=1, description="需要分析的一段用户输入。")


class MemorySearchRequest(BaseModel):
    # 搜索记忆时需要 user_id，因为不同用户的长期记忆不能混在一起。
    user_id: str = Field(min_length=1, description="要检索哪个用户的记忆。")
    query: str = Field(min_length=1, description="当前问题，用它匹配相关长期记忆。")
    limit: int = Field(default=5, ge=1, le=20, description="最多返回几条记忆。")


class MemoryCandidate(BaseModel):
    # MemoryCandidate 是从对话中抽取出的“候选记忆”，还不一定已经入库。
    # memory_type 用枚举限制范围，避免后端出现不可控分类。
    memory_type: MemoryType
    key: str
    value: str
    source_text: str
    confidence: float = Field(ge=0, le=1)
    reason: str


class MemoryResponse(BaseModel):
    # MemoryResponse 是返回给前端看的记忆 DTO。
    # 注意它和 ORM UserMemory 不同：ORM 负责入库，DTO 负责稳定接口结构。
    memory_id: str
    user_id: str
    memory_type: str
    key: str
    value: str
    source_text: str
    confidence: float
    created_at: str
    updated_at: str
    last_used_at: str | None


class ChatResponse(BaseModel):
    answer: str
    user_id: str
    used_memories: list[MemoryResponse]
    extracted_memories: list[MemoryCandidate]
    saved_memory_count: int
    message_count: int

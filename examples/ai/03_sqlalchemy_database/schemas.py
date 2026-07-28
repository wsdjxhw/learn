from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    # 请求 DTO：创建会话时只需要 title。
    title: str
    discussion: str | None = None


class SessionRead(BaseModel):
    # 响应 DTO：返回给客户端的会话结构。
    id: int
    title: str
    created_at: datetime
    description: str | None = None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
    system_prompt: str = "You are a helpful assistant."


class MessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

from datetime import datetime

from pydantic import BaseModel, Field


class DatabaseNoteCreate(BaseModel):
    # 请求 DTO：客户端创建一条验证用笔记时，只需要传 title 和 content。
    # 类比 Java 里的 CreateDatabaseNoteRequest。
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)


class DatabaseNoteRead(BaseModel):
    # 响应 DTO：返回给客户端的结构。
    # 它和 ORM Model 很像，但职责不同：
    # - ORM Model 管数据库表。
    # - DTO 管接口输入输出。
    id: int
    title: str
    content: str
    created_at: datetime

    class Config:
        # 让 Pydantic 可以从 SQLAlchemy ORM 对象读取字段。
        # 没有它，response_model 无法直接把 ORM 对象转成 JSON。
        from_attributes = True

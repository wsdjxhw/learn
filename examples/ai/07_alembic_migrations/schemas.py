from datetime import datetime

from pydantic import BaseModel, Field


class ArticleCreate(BaseModel):
    # 请求 DTO，类比 Java 里的 CreateArticleRequest。
    # 它只描述接口允许客户端传什么，不等于数据库表结构。
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class ArticleStatusUpdate(BaseModel):
    # 专门更新状态的 DTO。
    # 单独建 DTO 是为了让接口语义更清楚：这里只允许改状态，不允许顺手改标题正文。
    status: str = Field(pattern="^(draft|published|archived)$")


class ArticleRead(BaseModel):
    # 响应 DTO，类比 Java 里的 ArticleResponse。
    # from_attributes=True 让 Pydantic 能从 ORM 对象读取字段。
    id: int
    title: str
    content: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

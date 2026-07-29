from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class DatabaseNote(Base):
    # 这个 ORM Model 对应 database_notes 表。
    # 类比 Java 里的 Entity：它描述“数据库里一行数据长什么样”。
    #
    # 本模块不用聊天、RAG 或后台任务，是故意把业务简化。
    # 这样你可以把注意力放在：同一套 Model 如何从 SQLite 切到 PostgreSQL。
    __tablename__ = "database_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # String(120) 在 SQLite 和 PostgreSQL 都能使用。
    # PostgreSQL 会更认真地执行长度、类型等约束；SQLite 更宽松。
    title: Mapped[str] = mapped_column(String(120), nullable=False)

    # Text 适合保存较长文本。
    # 注意：DTO 负责校验“请求里有没有 content”，ORM 负责描述“表里如何保存 content”。
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # server_default=func.now() 表示 created_at 由数据库生成。
    # 这能帮助你观察 SQLite 和 PostgreSQL 对时间字段的返回差异。
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

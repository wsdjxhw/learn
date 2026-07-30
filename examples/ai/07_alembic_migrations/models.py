from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class KnowledgeArticle(Base):
    # ORM Model，类比 Java 里的 Entity。
    # 当前代码期望数据库里有 knowledge_articles 表。
    #
    # 注意：Alembic 模块里，Model 只代表“代码期望的最新结构”。
    # 数据库真实结构要靠迁移文件一步一步升级到这个状态。
    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # status 是第二个迁移版本新增的字段。
    # 它不是为了做“加字段练习”，而是用来学习已有表和已有数据如何安全变更。
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable = True
    )

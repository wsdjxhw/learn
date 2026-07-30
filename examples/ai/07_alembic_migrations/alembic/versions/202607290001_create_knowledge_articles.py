"""create knowledge articles table

Revision ID: 202607290001
Revises:
Create Date: 2026-07-29 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202607290001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # upgrade 表示“把数据库结构向前升级”。
    # 第一个迁移版本负责创建 knowledge_articles 表。
    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_articles_id", "knowledge_articles", ["id"])


def downgrade() -> None:
    # downgrade 表示“把数据库结构回退到上一个版本”。
    # 回退第一个版本时，会删除整张业务表；真实项目执行前必须确认数据风险。
    op.drop_index("ix_knowledge_articles_id", table_name="knowledge_articles")
    op.drop_table("knowledge_articles")

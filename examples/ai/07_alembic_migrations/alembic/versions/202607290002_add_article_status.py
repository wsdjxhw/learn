"""add status to knowledge articles

Revision ID: 202607290002
Revises: 202607290001
Create Date: 2026-07-29 00:00:02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202607290002"
down_revision: Union[str, None] = "202607290001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 第二个迁移模拟真实项目常见需求：
    # 表已经上线并有数据，现在要新增一个非空字段 status。
    #
    # 关键点：不能只写 nullable=False。
    # 如果表里已经有旧数据，旧数据没有 status，会违反非空约束。
    # server_default="draft" 让数据库给旧数据和未显式传值的新数据补默认值。
    with op.batch_alter_table("knowledge_articles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="draft",
            )
        )
        batch_op.create_index("ix_knowledge_articles_status", ["status"])


def downgrade() -> None:
    # 回滚这个迁移会删除 status 字段。
    # 这能让你观察：数据库结构回去了，但当前 Python 代码仍然期望 status 存在。
    # 这种“代码版本”和“数据库版本”不匹配，是生产事故的常见来源。
    with op.batch_alter_table("knowledge_articles") as batch_op:
        batch_op.drop_index("ix_knowledge_articles_status")
        batch_op.drop_column("status")

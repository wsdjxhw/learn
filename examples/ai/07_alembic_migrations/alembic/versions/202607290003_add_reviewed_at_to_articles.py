"""add reviewed_at to articles

Revision ID: 202607290003
Revises: 202607290002
Create Date: 2026-07-30 12:10:17.935937
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202607290003"
down_revision: Union[str, None] = "202607290002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 本次迁移只做一件事：给文章表增加 reviewed_at。
    # reviewed_at 允许为空，因为旧文章历史上可能确实没有审核时间。
    op.add_column(
        "knowledge_articles",
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    # 回滚本次迁移时，只删除 reviewed_at。
    op.drop_column("knowledge_articles", "reviewed_at")

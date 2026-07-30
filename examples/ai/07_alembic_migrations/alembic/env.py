from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# 让 alembic/env.py 能导入上一级目录里的 database.py 和 models.py。
# 这相当于告诉 Python：“当前模块根目录也可以作为 import 搜索路径”。
MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from database import get_database_url  # noqa: E402
from models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata 是 Alembic 自动生成迁移时会读取的“当前代码结构”。
# 它来自 SQLAlchemy ORM 的 Base.metadata。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # offline 模式不会真的连接数据库，只生成 SQL 文本。
    # 初学阶段主要使用 online 模式，但保留它是 Alembic 标准结构。
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # online 模式会真实连接数据库并执行迁移。
    # python -m alembic upgrade head 走的就是这个流程。
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

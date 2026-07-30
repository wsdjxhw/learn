import os
from pathlib import Path
from typing import Any, Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 只读取当前模块自己的 .env。
# 如果多个示例目录都有 .env，这样可以避免误连到别的模块数据库。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

MODULE_DIR = Path(__file__).parent
DEFAULT_DATABASE_URL = "sqlite:///./alembic_migrations.db"
EXPECTED_ALEMBIC_HEAD = "202607290003"


class Base(DeclarativeBase):
    # 所有 ORM Model 的父类。
    # SQLAlchemy 通过 Base.metadata 收集当前代码期望的表结构。
    # Alembic 的 env.py 会读取这个 metadata，再和数据库当前结构对比。
    pass


def get_database_url() -> str:
    # DATABASE_URL 是数据库连接配置。
    # SQLite 的 ./ 容易受启动目录影响，所以这里转成当前模块目录下的绝对路径。
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if database_url.startswith("sqlite:///./"):
        db_name = database_url.replace("sqlite:///./", "", 1)
        return f"sqlite:///{MODULE_DIR.joinpath(db_name).as_posix()}"
    return database_url


def build_connect_args(database_url: str) -> dict[str, Any]:
    # SQLite 在多线程场景下需要关闭同线程限制。
    # PostgreSQL 不需要 check_same_thread。
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    get_database_url(),
    connect_args=build_connect_args(get_database_url()),
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    # FastAPI 依赖函数。
    # db: Session = Depends(get_db) 可以理解成 FastAPI 自动注入数据库会话。
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_kind() -> str:
    # dialect 表示 SQLAlchemy 当前连接的是哪类数据库，例如 sqlite 或 postgresql。
    return engine.dialect.name


def get_safe_database_url() -> str:
    # 返回隐藏密码后的数据库连接串，方便调试但不泄露密码。
    return str(engine.url.render_as_string(hide_password=True))


def get_alembic_version() -> str | None:
    # Alembic 会用 alembic_version 表记录当前数据库结构版本。
    # 如果这个表不存在，说明数据库还没执行过迁移。
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return None

    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def list_table_details() -> list[dict[str, Any]]:
    # 读取当前数据库真实存在的表和列。
    # 查列名,和他的数据类型,默认值还有是否可空
    # 这能帮助你观察 upgrade / downgrade 后表结构到底有没有变化。
    inspector = inspect(engine)
    tables: list[dict[str, Any]] = []
    for table_name in inspector.get_table_names():
        columns = []
        for column in inspector.get_columns(table_name):
            columns.append(
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": column["nullable"],
                    "default": column.get("default"),
                }
            )
        tables.append({"name": table_name, "columns": columns})
    return tables


def check_connection() -> dict[str, Any]:
    # 数据库健康检查：只验证连接和执行最小 SQL，不依赖业务表。
    result: dict[str, Any] = {
        "ok": False,
        "database_kind": get_database_kind(),
        "driver": engine.dialect.driver,
        "database_url": get_safe_database_url(),
        "expected_alembic_head": EXPECTED_ALEMBIC_HEAD,
    }

    try:
        with engine.connect() as connection:
            result["probe"] = connection.scalar(text("SELECT 1"))
            if get_database_kind() == "postgresql":
                result["current_database"] = connection.scalar(text("SELECT current_database()"))
                result["current_schema"] = connection.scalar(text("SELECT current_schema()"))
            result["current_alembic_version"] = get_alembic_version()
            result["ok"] = True
            return result
    except SQLAlchemyError as exc:
        result["error_type"] = exc.__class__.__name__
        result["error"] = str(exc)
        result["hint"] = build_database_error_hint(exc)
        return result


def build_database_error_hint(exc: SQLAlchemyError) -> str:
    # 把常见数据库错误转成学习者能行动的提示。
    # 正式项目里错误细节通常进日志，接口只返回更克制的信息。
    message = str(exc).lower()
    if "no such table" in message or "undefinedtable" in message:
        return "业务表还不存在。先执行 python -m alembic upgrade head。"
    if "no such column" in message or "undefinedcolumn" in message:
        return "数据库结构落后于当前代码。执行 python -m alembic upgrade head。"
    if "password authentication failed" in message:
        return "PostgreSQL 用户名或密码错误。检查 .env 里的 DATABASE_URL。"
    if "database" in message and "does not exist" in message:
        return "PostgreSQL 数据库不存在。先创建 DATABASE_URL 指向的数据库。"
    if "connection refused" in message or "could not connect" in message:
        return "数据库服务可能没启动，或 host/port 写错。"
    return "查看 error 字段，优先检查迁移是否执行、DATABASE_URL 是否正确。"

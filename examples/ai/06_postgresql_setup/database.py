import os
from pathlib import Path
from typing import Any, Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 只读取当前模块目录下的 .env，避免误读别的示例模块配置。
# .env 适合放本机配置；.env.example 用来告诉别人需要哪些配置项。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

MODULE_DIR = Path(__file__).parent
DEFAULT_DATABASE_URL = "sqlite:///./postgresql_setup.db"


class Base(DeclarativeBase):
    # 所有 ORM Model 都继承 Base。
    # 可以类比 Java 项目里所有 Entity 都被 ORM 框架统一管理。
    # SQLAlchemy 通过 Base.metadata 收集“有哪些表、字段和关系”。
    pass


def get_database_url() -> str:
    # DATABASE_URL 是这个模块最重要的配置。
    # SQLite 示例通常写 sqlite:///./xxx.db，其中 ./ 表示“当前工作目录”。
    # 初学时如果从不同目录启动 uvicorn，很容易把 db 文件生成到错误位置。
    # 所以这里把 ./ 转成当前文件所在目录下的绝对路径，保证行为稳定。
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if database_url.startswith("sqlite:///./"):
        db_name = database_url.replace("sqlite:///./", "", 1)
        return f"sqlite:///{MODULE_DIR.joinpath(db_name).as_posix()}"
    return database_url


def get_safe_database_url() -> str:
    # 健康检查里需要展示“当前连到哪里”，但不能把密码直接返回给前端。
    # SQLAlchemy 的 URL 对象可以把 password 隐藏成 ***。
    return str(engine.url.render_as_string(hide_password=True))


def get_database_kind() -> str:
    # dialect 是 SQLAlchemy 对不同数据库的统一叫法。
    # sqlite、postgresql、mysql 都是 dialect。
    return engine.dialect.name


def build_connect_args(database_url: str) -> dict[str, Any]:
    # SQLite 有一个线程限制：默认连接只能在创建它的线程里使用。
    # FastAPI 开发服务可能在不同线程处理请求，所以学习项目里关闭这个限制。
    # PostgreSQL 不需要这个参数。
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


def create_tables() -> None:
    # create_all 会根据 ORM Model 创建还不存在的表。
    # 本模块先保留它，是为了专注学习“连接 PostgreSQL”。
    # 下一模块 Alembic 会解释为什么正式项目不能长期依赖 create_all 管表结构。
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    # FastAPI 依赖函数：接口参数写 db: Session = Depends(get_db) 后，
    # FastAPI 会在每个请求开始时创建 Session，请求结束后关闭。
    # 类比 Java 里 Controller 方法拿到一个数据库操作上下文。
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def list_table_names() -> list[str]:
    # inspect(engine) 会读取当前数据库的元信息，例如有哪些表。
    # 这比“猜测表有没有创建”更可靠。
    inspector = inspect(engine)
    return inspector.get_table_names()


def check_connection() -> dict[str, Any]:
    # 这个函数专门服务 /db/health。
    # 它不抛 HTTPException，而是把连接成功或失败都整理成 JSON，
    # 方便学习者在 /docs 里直接看到真实错误。
    result: dict[str, Any] = {
        "ok": False,
        "database_kind": get_database_kind(),
        "driver": engine.dialect.driver,
        "database_url": get_safe_database_url(),
    }

    try:
        with engine.connect() as connection:
            # SELECT 1 是最小探针：不依赖任何业务表，只验证数据库能否连接和执行 SQL。
            probe_value = connection.scalar(text("SELECT 1"))
            result["probe"] = probe_value

            if get_database_kind() == "postgresql":
                # 这些 PostgreSQL 专有信息能确认“现在真的连到了哪个库、哪个 schema”。
                result["current_database"] = connection.scalar(text("SELECT current_database()"))
                result["current_schema"] = connection.scalar(text("SELECT current_schema()"))
                version = connection.scalar(text("SELECT version()"))
                result["server_version"] = version

            result["tables"] = list_table_names()
            result["ok"] = True
            return result
    except SQLAlchemyError as exc:
        result["error_type"] = exc.__class__.__name__
        result["error"] = str(exc)
        result["hint"] = build_connection_error_hint(exc)
        return result


def build_connection_error_hint(exc: SQLAlchemyError) -> str:
    # 真实项目里错误信息会写日志，接口只返回安全提示。
    # 学习阶段先把常见连接错误转成可操作的排查方向。
    message = str(exc).lower()
    if "password authentication failed" in message:
        return "用户名或密码错误。检查 DATABASE_URL 里的 username/password。"
    if "database" in message and "does not exist" in message:
        return "数据库不存在。先在 PostgreSQL 中创建 DATABASE_URL 指向的数据库。"
    if "connection refused" in message or "could not connect" in message:
        return "PostgreSQL 服务可能没启动，或 host/port 写错。"
    if "no such table" in message or "undefinedtable" in message:
        return "数据库能连上，但表还没创建。调用 POST /setup/create-tables。"
    return "查看 error 字段，优先检查 DATABASE_URL、数据库服务状态和表是否已创建。"

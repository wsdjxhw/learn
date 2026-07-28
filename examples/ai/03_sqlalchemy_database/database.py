import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 读取当前示例目录下的 .env。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

DEFAULT_DATABASE_URL = "sqlite:///./chat_sqlalchemy.db"
MODULE_DIR = Path(__file__).parent


class Base(DeclarativeBase):
    # 所有 ORM 模型都会继承 Base。
    # SQLAlchemy 会通过 Base.metadata 知道项目里有哪些表。
    pass


def get_database_url() -> str:
    # SQLite 适合本地学习；PostgreSQL 适合后续生产环境。
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if database_url.startswith("sqlite:///./"):
        db_name = database_url.replace("sqlite:///./", "", 1)
        return f"sqlite:///{MODULE_DIR.joinpath(db_name).as_posix()}"
    return database_url


connect_args = {}
if get_database_url().startswith("sqlite"):
    # SQLite 默认限制同一个连接只能在创建它的线程使用。
    # FastAPI 开发环境下关闭这个限制更方便。
    connect_args = {"check_same_thread": False}

engine = create_engine(
    get_database_url(),
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def create_tables() -> None:
    # 学习阶段先用 create_all 自动建表。
    # 正式项目后面会改成 Alembic 管理数据库迁移。
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    # FastAPI 依赖函数：每个请求创建一个数据库会话，请求结束后关闭。
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

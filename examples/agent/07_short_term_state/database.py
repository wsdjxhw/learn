from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from settings import get_settings


class Base(DeclarativeBase):
    # Base 是所有 ORM Model 的父类。
    # Java 类比：ORM Model 类似 Entity，表示数据库里的表结构。
    pass


settings = get_settings()

# connect_args 只在 SQLite 里需要。
# FastAPI 的后台任务和请求处理可能在不同线程里访问数据库。
# check_same_thread=False 允许同一个 SQLite 文件被这些线程安全地打开连接。
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

# SessionLocal 是数据库会话工厂。
# Java 类比：可以粗略理解成每次请求拿到的 EntityManager / Repository 操作入口。
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # create_all() 会根据 ORM Model 创建表。
    # 生产项目会用 Alembic 迁移管理表结构，本教学模块为了先能运行，使用 create_all。
    import models

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    # get_db() 是 FastAPI 依赖注入函数。
    # db: Session = Depends(get_db) 可以理解成 FastAPI 自动给接口方法注入数据库会话。
    db = SessionLocal()
    try:
        yield db
    finally:
        # finally 表示无论接口成功还是失败，最后都关闭数据库连接。
        db.close()

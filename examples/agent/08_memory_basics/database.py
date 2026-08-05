from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from settings import get_settings


class Base(DeclarativeBase):
    # Base 是所有 ORM Model 的父类。
    # Java 类比：继承 Base 的类类似 Entity，会映射到数据库表。
    pass


settings = get_settings()

# SQLite 在 FastAPI 请求和后台线程场景下经常需要 check_same_thread=False。
# 本模块没有后台任务，但沿用这个配置，方便后续和短期状态模块衔接。
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

# SessionLocal 是数据库会话工厂。
# Java 类比：可以粗略理解成每个请求拿到的 EntityManager / Repository 操作入口。
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # create_all() 会根据 ORM Model 创建表。
    # 正式生产环境应该使用 Alembic 管理迁移；教学模块先保证能运行。
    import models

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    # get_db() 是 FastAPI 依赖注入函数。
    # db: Session = Depends(get_db) 表示 FastAPI 自动给接口函数注入数据库会话。
    db = SessionLocal()
    try:
        yield db
    finally:
        # finally 表示无论接口成功还是抛异常，最后都关闭数据库连接。
        db.close()

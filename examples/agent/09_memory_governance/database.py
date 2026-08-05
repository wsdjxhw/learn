from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from settings import get_settings


class Base(DeclarativeBase):
    # Base 是所有 ORM Model 的父类。
    # Java 类比：继承 Base 的类类似 Entity，会映射到数据库表。
    pass


settings = get_settings()

# SQLite 在多线程访问时需要这个参数。
# FastAPI 后续如果使用后台任务或测试客户端，可能会跨线程访问同一个 SQLite 文件。
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

# SessionLocal 是数据库会话工厂。
# Java 类比：可以粗略理解成 Repository / EntityManager 的入口。
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # create_all() 根据 ORM Model 创建表。
    # 本模块先保证学习者能跑通；生产环境会用 Alembic 管理表结构变更。
    import models

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    # get_db() 是 FastAPI 依赖注入函数。
    # db: Session = Depends(get_db) 表示接口函数自动获得一个数据库会话。
    db = SessionLocal()
    try:
        yield db
    finally:
        # finally 保证无论接口成功还是异常，最后都会关闭数据库连接。
        db.close()

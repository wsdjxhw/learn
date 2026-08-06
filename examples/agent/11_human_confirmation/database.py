from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from settings import get_settings


class Base(DeclarativeBase):
    # Base 是所有 ORM Model 的父类。
    # Java 类比：继承 Base 的类类似 Entity，会映射成数据库表。
    pass


settings = get_settings()

# SQLite 在 FastAPI 测试客户端或后台线程里可能跨线程访问。
# check_same_thread=False 是 SQLite 特有参数，PostgreSQL 不需要。
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

# SessionLocal 是数据库会话工厂。
# Java 类比：可以粗略理解成创建 EntityManager / Repository 操作入口的工厂。
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # 教学模块用 create_all() 自动建表，保证第一次运行就能用。
    # 生产项目不建议这样管理表结构，应该使用 Alembic 迁移。
    import models

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    # get_db() 是 FastAPI 依赖注入函数。
    # db: Session = Depends(get_db) 表示接口函数会自动拿到一个数据库会话。
    db = SessionLocal()
    try:
        yield db
    finally:
        # finally 保证无论接口成功还是抛异常，数据库连接最后都会关闭。
        db.close()

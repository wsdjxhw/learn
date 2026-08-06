"""
database.py - 数据库引擎与会话管理

职责：创建 SQLAlchemy 引擎、定义 Base（所有 ORM 模型的父类）、
     提供 get_db() 依赖，让每个接口拿到独立的数据库会话。

和模块 04/05 的 database.py 结构一致，区别是：
- 这里保存的是“文档知识库”，而不是聊天消息；
- 用 SQLite 便于无 Docker 也能跑（真实项目换 PostgreSQL 只需改 DATABASE_URL）。

为什么需要 get_db()？
FastAPI 的依赖注入（Depends）会在每个请求里调用 get_db()，
自动创建一个 Session 并在请求结束时关闭。这保证：
1. 每次请求的数据库操作互相独立；
2. 不会忘记关连接（连接泄漏是真实项目最常见的坑之一）。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from settings import settings

# 创建数据库引擎。
# connect_args 里的 check_same_thread=False 是 SQLite 专用：
# SQLite 默认只允许创建它的线程访问，而 FastAPI 可能在不同线程处理请求，
# 必须关掉这个限制，否则会报 "SQLite objects created in a thread can only be used in that same thread"。
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

# SessionLocal 是一个“会话工厂”，调用 SessionLocal() 才真正创建一次会话。
# 类比 Java：类似 Hibernate 的 SessionFactory。
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 是所有 ORM 模型的父类。模型类要继承它，SQLAlchemy 才会认识这些表。
# 类比 Java：JPA 里的 @Entity 基类；模型声明在哪里，表结构就定义在哪里。
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入函数：给接口提供一个数据库会话。

    yield 是 Python 生成器语法。FastAPI 依赖注入对生成器的约定是：
    yield 之前的部分在请求开始时执行（这里是创建会话），
    yield 之后的部分在请求结束时执行（这里是关闭会话）。

    类比 Java：类似 Spring 里 @Scope("request") 的会话，
    request 结束自动 close，避免连接泄漏。
    """
    db = SessionLocal()
    try:
        yield db  # 把会话交给调用方（接口函数）
    finally:
        db.close()  # 无论接口成功还是抛异常，都会执行关闭

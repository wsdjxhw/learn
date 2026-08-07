"""
database.py —— 数据库引擎与会话

职责：创建数据库引擎（engine）和会话工厂（SessionLocal），并提供一个
FastAPI 依赖 get_db，让每个接口自动拿到一个数据库会话。

这里把"怎么连数据库"和"数据长什么样（见 models.py）"分开，
这正是分层设计的一部分：database.py 管连接，models.py 管表结构。

初学者容易卡住的地方：
- engine：负责真正和数据库建立连接，是整个应用共享的（只创建一次）。
- SessionLocal：一个"会话工厂"，它不是会话本身，而是用来造会话的函数。
  每个请求应该用一个新的 Session，用完就关，避免数据串在一起。
- get_db 用了 yield 语法，这是 FastAPI 依赖注入的固定写法（详见函数内注释）。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from settings import settings

# create_engine 根据连接串创建引擎。
# 参数说明：
#   connect_args={"check_same_thread": False}：
#     SQLite 默认只允许创建它的线程访问，而 FastAPI 的接口可能跑在不同线程池线程上，
#     必须关掉这个限制才能在线程池里正常访问数据库（PostgreSQL 等数据库没有这个问题）。
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

# sessionmaker 造出一个"会话工厂"，调用它()就能得到一个新的 Session。
# 参数说明：
#   autocommit=False：事务要手动 commit（大多数 ORM 的默认行为，符合真实项目习惯）。
#   expire_on_commit=False：commit 之后对象上的数据仍然可读。
#     如果不设，commit 后你再访问对象的字段，SQLAlchemy 会再查一次数据库，
#     初学者常常在这里莫名报错，所以提前关掉。
SessionLocal = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)


def init_db():
    """建表：把 models.py 里定义的所有表结构同步到数据库。

    注意：教学版用 create_all 建表，简单方便。
    但真实项目绝不能在生产环境用 create_all，因为表结构一旦变更它不会帮你改，
    正式项目用 Alembic 迁移工具（本项目的 examples/ai/07_alembic_migrations 学过）。
    """
    from models import Base  # 在这里导入，确保所有 ORM 表都已注册到 Base

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖注入函数：给每个请求一个独立的数据库会话。

    这里的 yield 是初学者最容易卡住的语法：
    普通函数用 return 一次性返回结果；带 yield 的函数叫"生成器"。
    FastAPI 会在请求开始时进入这个函数，把 yield 出来的 db 注入给接口；
    等请求结束后，会回到 yield 下面的代码执行 db.close()，把资源释放掉。
    这样我们不用在每一个接口里手动关数据库连接。
    """
    db = SessionLocal()  # 造一个新的会话
    try:
        yield db         # 把 db 交给使用它的接口
    finally:
        db.close()       # 请求结束（无论成功失败）都会关闭会话，防止连接泄漏

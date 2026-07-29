# 逐段讲解

这一节学习 PostgreSQL 连接。

如果你对 PostgreSQL 本身还不熟，先读：

[POSTGRESQL_BASICS.md](POSTGRESQL_BASICS.md)

如果你还没安装 PostgreSQL，再读：

[POSTGRESQL_INSTALL_WINDOWS.md](POSTGRESQL_INSTALL_WINDOWS.md)

前面你已经见过 SQLite 和 SQLAlchemy。这个模块要补上的能力是：

```text
同一套 Python ORM 代码，如何切换到真正的 PostgreSQL 数据库
```

## 为什么要学 PostgreSQL

SQLite 很适合学习：

- 不需要安装服务。
- 一个 `.db` 文件就是数据库。
- 启动成本低。

但真实项目通常需要 PostgreSQL：

- 多个后端进程可以同时访问。
- 类型、约束、事务更严格。
- 更适合部署到服务器。
- 后续可以扩展向量检索、日志、任务状态等能力。

## 文件分工

`database.py`

负责：

- 读取 `.env` 里的 `DATABASE_URL`。
- 创建 SQLAlchemy `engine`。
- 创建 FastAPI 可注入的 `Session`。
- 提供数据库健康检查。
- 查询当前数据库有哪些表。

`models.py`

负责 ORM Model。

可以类比 Java 里的 Entity。这里的 `DatabaseNote` 对应数据库里的 `database_notes` 表。

`schemas.py`

负责请求和响应 DTO。

不要把 DTO 和 ORM Model 混在一起：

```text
schemas.py 管接口输入输出
models.py  管数据库表结构
```

`main.py`

负责 FastAPI 接口。

可以类比 Java Controller：接收请求、调用数据库会话、返回响应。

## `DATABASE_URL`

SQLite 的连接串：

```text
sqlite:///./postgresql_setup.db
```

PostgreSQL 的连接串：

```text
postgresql+psycopg://postgres:postgres@localhost:5432/ai_learn
```

拆开理解：

```text
postgresql+psycopg  使用 PostgreSQL，并通过 psycopg 驱动连接
postgres           用户名
postgres           密码
localhost          数据库服务地址
5432               默认端口
ai_learn           数据库名
```

## `engine`

`database.py` 里最关键的是：

```python
engine = create_engine(...)
```

`engine` 可以理解成“数据库连接工厂”。

它不是某一条业务数据，也不是某一次查询结果，而是 SQLAlchemy 用来知道：

- 连哪种数据库。
- 用哪个驱动。
- 地址、端口、账号密码是什么。
- 如何创建连接。

## `Session`

```python
SessionLocal = sessionmaker(...)
```

`Session` 表示一次数据库操作上下文。

接口里这段代码：

```python
db: Session = Depends(get_db)
```

意思是：FastAPI 每次请求进来时，自动创建一个数据库会话传给接口函数。

可以类比 Java 里 Controller 方法拿到一个 Repository 背后的数据库操作上下文。

## `/db/health`

这个接口执行：

```sql
SELECT 1
```

它的价值是：不依赖业务表，只验证数据库能不能连接、能不能执行最小 SQL。

如果 PostgreSQL 配错，常见问题包括：

- 服务没启动。
- 端口不是 `5432`。
- 用户名或密码错误。
- 数据库 `ai_learn` 还没创建。
- Python 没安装 PostgreSQL 驱动。

`/db/health` 会尽量把这些错误整理成 `hint`，方便排查。

## `/setup/create-tables`

这个接口调用：

```python
Base.metadata.create_all(bind=engine)
```

它会根据 `models.py` 里的 ORM Model 创建表。

本模块保留这个接口，是为了让你聚焦连接 PostgreSQL 和验证写入。

但正式项目不能长期依赖它管理表结构，因为它只擅长“创建不存在的表”，不擅长安全地管理已有表变更。

下一模块 Alembic 会学习：

- 生成迁移文件。
- 执行升级。
- 执行回滚。
- 记录数据库结构版本。

## 你要掌握的核心链路

```text
.env
-> DATABASE_URL
-> create_engine()
-> Session
-> ORM Model
-> create_tables()
-> POST /notes 写入
-> GET /notes 读取
-> /db/health 验证当前数据库
```

学完这一节，你应该能判断：

- 当前服务连的是 SQLite 还是 PostgreSQL。
- PostgreSQL 连接失败应该从哪里排查。
- 表是否已经创建。
- 数据是否真的写入当前数据库。
- 为什么下一步要学习 Alembic。

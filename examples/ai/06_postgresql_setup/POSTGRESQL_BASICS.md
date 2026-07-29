# PostgreSQL 零基础入门

这份文档放在代码讲解之前读。

如果你的电脑还没有安装 PostgreSQL，读完本文后继续看：

[POSTGRESQL_INSTALL_WINDOWS.md](POSTGRESQL_INSTALL_WINDOWS.md)

如果你对 PostgreSQL 是零基础，不要一上来就改 `.env`。先把下面这些概念弄清楚：

```text
PostgreSQL 服务
-> 账号和密码
-> 数据库
-> schema
-> 表
-> 行和列
-> SQL
-> DATABASE_URL
-> FastAPI 通过 SQLAlchemy 连接数据库
```

## PostgreSQL 是什么

PostgreSQL 是一个关系型数据库。

关系型数据库可以先理解成：

```text
很多张表
每张表有固定列
每一行是一条数据
表和表之间可以通过 id 建立关系
```

如果你学过 Java 后端，可以类比：

```text
PostgreSQL       MySQL / Oracle / SQL Server 这一类数据库
database         一个具体项目的数据空间
table            一张表
row              表里的一条记录
column           表里的一个字段
primary key      主键
foreign key      外键
SQLAlchemy Model Java Entity
Pydantic Schema  Java DTO
```

本项目之前用过 SQLite。SQLite 和 PostgreSQL 都是关系型数据库，但使用方式不一样。

## SQLite 和 PostgreSQL 的核心区别

SQLite 更像一个本地文件：

```text
chat.db
```

Python 程序直接读写这个文件，不需要启动数据库服务。

PostgreSQL 更像一个独立运行的服务：

```text
FastAPI 应用 -> 连接 PostgreSQL 服务 -> 操作数据库
```

所以 PostgreSQL 会多出这些概念：

- 服务是否启动。
- 服务监听哪个端口。
- 用户名是什么。
- 密码是什么。
- 要连接哪个数据库。
- 当前用户有没有权限。

这也是为什么 PostgreSQL 初学时更容易报连接错误。

## 先理解“服务”

PostgreSQL 安装后，会在电脑上运行一个数据库服务。

服务可以理解成一个长期运行的后台程序：

```text
PostgreSQL 服务一直开着
FastAPI 需要时去连接它
```

默认情况下，PostgreSQL 通常监听：

```text
localhost:5432
```

含义：

- `localhost`：本机。
- `5432`：PostgreSQL 默认端口。

如果服务没启动，你的 Python 代码通常会报类似：

```text
connection refused
could not connect
```

这不是代码逻辑错，而是数据库服务没连上。

## 账号、密码和角色

PostgreSQL 里有用户，也常叫 role。

你连接数据库时，需要提供：

```text
用户名
密码
```

例如：

```text
postgres / postgres
```

`postgres` 通常是安装 PostgreSQL 时创建的默认超级用户。

学习阶段可以先用默认用户，但要知道：

```text
正式项目不应该长期用超级用户连接业务应用
```

后面真正做项目时，通常会给应用单独创建一个用户，只给它需要的权限。

## 数据库 database

PostgreSQL 服务里可以有多个数据库。

可以理解成：

```text
一个 PostgreSQL 服务
里面可以有 ai_learn、test_db、production_db 等多个数据库
```

本模块文档里使用的例子是：

```text
ai_learn
```

这意味着你需要先创建一个叫 `ai_learn` 的数据库，然后 FastAPI 才能连接它。

如果数据库不存在，连接时可能报：

```text
database "ai_learn" does not exist
```

这个错误的意思不是表不存在，而是整个数据库还没创建。

## schema 是什么

PostgreSQL 里，database 下面还有一层 schema。

默认 schema 通常叫：

```text
public
```

可以先这样理解：

```text
PostgreSQL 服务
-> database: ai_learn
-> schema: public
-> table: database_notes
```

初学阶段大部分时间都用默认的 `public` schema，不需要自己设计复杂 schema。

但你在 `/db/health` 里会看到：

```json
{
  "current_schema": "public"
}
```

它就是在告诉你：当前连接进入的是哪个 schema。

## 表 table

表是保存数据的地方。

本模块的 ORM Model 是：

```python
class DatabaseNote(Base):
    __tablename__ = "database_notes"
```

这表示数据库里会有一张表：

```text
database_notes
```

这张表大概长这样：

| id | title | content | created_at |
| --- | --- | --- | --- |
| 1 | postgres-check | 验证连接 | 2026-07-29 10:00:00 |

每一行是一条 note。

每一列是一个字段。

## 主键 primary key

主键是每一行数据的唯一标识。

本模块里：

```python
id: Mapped[int] = mapped_column(primary_key=True, index=True)
```

这表示 `id` 是主键。

主键的作用是：

- 唯一定位一条数据。
- 被其他表引用。
- 更新、删除、查询时更可靠。

如果类比 Java：

```text
Entity 里的 id 字段通常就是数据库主键
```

## 字段类型

PostgreSQL 比 SQLite 更严格。

例如本模块里：

```python
title: Mapped[str] = mapped_column(String(120), nullable=False)
content: Mapped[str] = mapped_column(Text, nullable=False)
created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

对应到数据库概念：

- `String(120)`：最多 120 个字符的字符串。
- `Text`：较长文本。
- `DateTime`：日期时间。
- `nullable=False`：不能为空。
- `server_default=func.now()`：默认值由数据库生成。

SQLite 有时比较宽松，PostgreSQL 会更认真地检查类型和约束。

这就是为什么真实项目更常用 PostgreSQL：它能更早暴露数据问题。

## SQL 是什么

SQL 是操作关系型数据库的语言。

你可以用 SQL 做这些事：

```sql
SELECT 1;
```

验证数据库能不能执行 SQL。

```sql
CREATE DATABASE ai_learn;
```

创建数据库。

```sql
SELECT * FROM database_notes;
```

查询表里的数据。

```sql
INSERT INTO database_notes (title, content)
VALUES ('hello', 'first note');
```

插入数据。

在本项目里，大部分 SQL 会由 SQLAlchemy 帮你生成。

但你仍然需要能读懂最基本的 SQL，因为排查数据库问题时经常会用到。

## psql 和 pgAdmin

安装 PostgreSQL 后，常见操作工具有两类。

`psql` 是命令行工具。

你可以在命令行里输入 SQL，例如：

```sql
CREATE DATABASE ai_learn;
```

pgAdmin 是图形界面工具。

你可以用它查看：

- 当前有哪些数据库。
- 当前有哪些表。
- 表里有哪些数据。
- SQL 执行结果。

学习阶段你可以任选一种。

如果你不熟命令行，用 pgAdmin 更直观。

如果你想练后端工程能力，建议逐步熟悉 `psql`。

## DATABASE_URL 是什么

FastAPI 不是直接“自动知道”数据库在哪里。

它需要一条连接串，也就是：

```text
DATABASE_URL
```

本模块的 PostgreSQL 示例：

```text
postgresql+psycopg://postgres:postgres@localhost:5432/ai_learn
```

拆开看：

```text
postgresql+psycopg://用户名:密码@主机:端口/数据库名
```

对应关系：

```text
postgresql+psycopg  数据库类型 + Python 驱动
postgres            用户名
postgres            密码
localhost           主机，本机
5432                端口
ai_learn            数据库名
```

如果你的密码是 `123456`，数据库名是 `ai_learn`，连接串就是：

```text
DATABASE_URL=postgresql+psycopg://postgres:123456@localhost:5432/ai_learn
```

## Python 驱动是什么

PostgreSQL 是数据库服务。

Python 不能凭空和它说话，需要一个驱动。

本模块使用：

```text
psycopg
```

所以 `requirements.txt` 里有：

```text
psycopg[binary]
```

连接串里也写：

```text
postgresql+psycopg
```

这表示：

```text
SQLAlchemy 使用 psycopg 驱动连接 PostgreSQL
```

## SQLAlchemy 在中间做什么

你现在的代码不是直接写很多 SQL，而是写 ORM Model：

```python
note = DatabaseNote(title=payload.title, content=payload.content)
db.add(note)
db.commit()
db.refresh(note)
```

SQLAlchemy 会把它转换成数据库操作。

可以类比 Java：

```text
Controller
-> DTO
-> Entity
-> Repository / ORM
-> PostgreSQL
```

在本项目里是：

```text
FastAPI 接口
-> Pydantic Schema
-> SQLAlchemy Model
-> SQLAlchemy Session
-> PostgreSQL
```

## create_all 是什么

本模块里有：

```python
Base.metadata.create_all(bind=engine)
```

它的作用是：

```text
根据 models.py 里的 ORM Model 创建还不存在的表
```

学习阶段可以这样做，因为它简单直观。

但正式项目不能只靠它，因为：

- 它不会可靠地记录数据库结构版本。
- 它不适合管理已有表字段变更。
- 它不擅长回滚。
- 它不能清楚告诉团队“这次数据库结构改了什么”。

所以下一模块要学 Alembic。

## 最小学习顺序

如果你是零基础，建议按这个顺序学：

1. 理解 PostgreSQL 是一个独立服务，不是一个 `.db` 文件。
2. 确认服务地址通常是 `localhost:5432`。
3. 知道连接需要用户名、密码、数据库名。
4. 创建一个数据库，例如 `ai_learn`。
5. 把 `.env` 里的 `DATABASE_URL` 改成 PostgreSQL。
6. 调用 `GET /db/health` 看连接是否成功。
7. 调用 `POST /setup/create-tables` 创建表。
8. 调用 `POST /notes` 写入一条数据。
9. 调用 `GET /notes` 读取数据。
10. 用 `/db/tables` 或 pgAdmin 确认表存在。

## 常见错误和排查方向

### 服务没启动

常见现象：

```text
connection refused
could not connect
```

排查：

- PostgreSQL 是否安装。
- PostgreSQL 服务是否启动。
- 端口是否是 `5432`。
- `DATABASE_URL` 里的 host/port 是否写对。

### 密码错误

常见现象：

```text
password authentication failed
```

排查：

- 用户名是否写对。
- 密码是否写对。
- 密码里如果有特殊字符，连接串可能需要 URL 编码。

### 数据库不存在

常见现象：

```text
database "ai_learn" does not exist
```

排查：

- 是否已经创建 `ai_learn`。
- `DATABASE_URL` 最后的数据库名是否拼错。

### 表不存在

常见现象：

```text
relation "database_notes" does not exist
```

排查：

- 是否调用过 `POST /setup/create-tables`。
- 当前连接的是不是你以为的那个数据库。
- `/db/tables` 里有没有 `database_notes`。

### 连的是 SQLite，不是 PostgreSQL

常见现象：

```json
{
  "database_kind": "sqlite"
}
```

排查：

- `.env` 是否真的修改了。
- 修改 `.env` 后是否重启了 `uvicorn`。
- 当前启动目录是不是 `examples/ai/06_postgresql_setup`。

## 本模块要达到的理解程度

学完这份文档和本模块代码后，你不需要成为数据库专家。

但你应该能清楚回答：

- PostgreSQL 为什么需要先启动服务。
- `localhost:5432` 是什么意思。
- `DATABASE_URL` 每一段是什么意思。
- database、schema、table 的层级关系。
- 为什么同一套 SQLAlchemy 代码可以切换 SQLite 和 PostgreSQL。
- `/db/health` 为什么比普通 `/health` 更能发现数据库问题。
- 为什么 `create_all` 只是学习阶段方案，下一步要学 Alembic。

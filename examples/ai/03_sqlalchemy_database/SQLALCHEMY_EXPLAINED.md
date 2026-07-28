# 逐段讲解

这一节开始学习 ORM。

## ORM 是什么

ORM 的意思是 Object Relational Mapping。

可以先理解成：

```text
Python class <-> 数据库表
Python 对象 <-> 表里的一行数据
```

Java 里常见的是 JPA / Hibernate。

SQLAlchemy 在这里的角色类似：

```text
SQLAlchemy -> JPA / Hibernate
models.py  -> Entity
schemas.py -> DTO
```

## `database.py`

这个文件负责数据库连接。

关键代码：

```python
engine = create_engine(...)
```

`engine` 表示数据库引擎，可以理解成“怎么连接数据库”。

```python
SessionLocal = sessionmaker(...)
```

`Session` 表示一次数据库操作上下文，类似 Java 里 Repository 操作背后的数据库会话。

```python
Base.metadata.create_all(bind=engine)
```

根据 ORM 模型创建数据库表。

学习阶段可以这么做，正式项目后面会用 Alembic 管理迁移。

## `models.py`

这个文件定义数据库表。

```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"
```

这表示 `ChatSession` 对应 `chat_sessions` 表。

```python
id: Mapped[int] = mapped_column(primary_key=True)
```

这表示 `id` 是主键。

```python
session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
```

这表示 `chat_messages.session_id` 关联 `chat_sessions.id`。

## `schemas.py`

这个文件定义接口层的 DTO。

不要把 `models.py` 和 `schemas.py` 混在一起理解：

```text
models.py  管数据库表
schemas.py 管接口输入输出
```

## `main.py`

这个文件负责接口。

```python
db: Session = Depends(get_db)
```

这表示 FastAPI 会在请求进来时自动给函数传一个数据库会话。

```python
db.add(session)
db.commit()
db.refresh(session)
```

含义：

- `add`：准备保存
- `commit`：提交到数据库
- `refresh`：把数据库生成的 id、created_at 刷回对象

## 你要掌握的核心链路

```text
请求 JSON
-> schemas.py DTO 校验
-> main.py 接口处理
-> models.py ORM 对象
-> database.py Session 保存
-> 数据库表
```

如果你学过 Java，可以类比成：

```text
Controller -> DTO -> Entity -> Repository -> Database
```

FastAPI 和 SQLAlchemy 只是换了一套 Python 写法。

# 逐段讲解

这一节学习 Alembic 数据库迁移。

如果你第一次接触迁移，先读：

[ALEMBIC_BASICS.md](ALEMBIC_BASICS.md)

## 文件分工

`database.py`

负责：

- 读取 `.env` 里的 `DATABASE_URL`。
- 创建 SQLAlchemy `engine`。
- 创建 FastAPI 可注入的 `Session`。
- 查询 `alembic_version`。
- 查看真实数据库表和列。
- 整理常见数据库错误提示。

`models.py`

负责 ORM Model。

注意：在 Alembic 模块里，ORM Model 代表“当前代码期望的最新表结构”，不代表数据库已经自动变成这个结构。

`schemas.py`

负责接口 DTO。

可以类比 Java 里的 Request / Response DTO。

`main.py`

负责 FastAPI 接口。

它不会在启动时调用 `create_all`。

这是本模块最重要的设计：让你亲自执行迁移，观察数据库结构版本变化。

`alembic/env.py`

Alembic 运行迁移时会执行这个文件。

它负责：

- 读取当前模块的 `DATABASE_URL`。
- 导入 ORM Model。
- 把 `Base.metadata` 交给 Alembic。
- 创建数据库连接并执行迁移。

`alembic/versions`

存放迁移文件。

每个迁移文件都是一个数据库结构版本。

## 为什么启动时不 create_all

前面模块启动时会自动建表，是为了降低学习门槛。

但本模块要学习的是：

```text
数据库结构必须由迁移文件管理
```

所以这里故意不调用：

```python
Base.metadata.create_all(bind=engine)
```

结果是：

- FastAPI 可以启动。
- `/health` 可以正常返回。
- 如果没有执行迁移，`/articles` 会报表不存在。

这就是正式项目里的真实情况：

```text
应用代码部署成功，不代表数据库结构也部署成功。
```

## `database.py`

关键配置：

```python
EXPECTED_ALEMBIC_HEAD = "202607290002"
```

它表示本模块当前代码期望的最新迁移版本。

接口 `GET /migration/status` 会对比：

```text
数据库当前版本
代码期望版本
```

如果两者不一致，就说明数据库结构可能落后。

## `get_alembic_version`

这个函数读取：

```text
alembic_version
```

如果表不存在，返回 `None`。

这通常表示：

```text
还没有执行过 alembic upgrade
```

## `models.py`

当前最新 Model 是：

```python
class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
```

字段包括：

- `id`
- `title`
- `content`
- `status`
- `created_at`

其中 `status` 是第二个迁移新增的字段。

如果你把数据库回滚到 `202607290001`，数据库里就没有 `status`，但 Python 代码还会尝试查询它。

这会制造一个非常有价值的观察：

```text
代码版本和数据库版本不匹配会导致运行时报错
```

## 迁移文件 1

文件：

```text
alembic/versions/202607290001_create_knowledge_articles.py
```

`upgrade` 创建表：

```python
op.create_table(...)
```

`downgrade` 删除表：

```python
op.drop_table(...)
```

这表示从空数据库进入第一版结构。

## 迁移文件 2

文件：

```text
alembic/versions/202607290002_add_article_status.py
```

它新增：

```text
status
```

关键是：

```python
server_default="draft"
```

这是为了处理已有旧数据。

如果旧表里已经有文章，新增 `NOT NULL` 字段时必须给旧数据一个合理默认值。

## `main.py`

`GET /migration/status`

用于确认数据库结构版本。

重点看：

- `current_version`
- `expected_head`
- `is_latest`

`GET /db/tables`

用于查看当前数据库真实有哪些表和列。

升级和回滚后都应该调用它观察变化。

`POST /articles`

创建文章。

如果没迁移，会报表不存在。

如果回滚到旧版本，会因为 `status` 不存在而报错。

这些报错不是低质量失败，而是在训练你识别数据库结构版本问题。

## 本模块核心链路

```text
启动 FastAPI
-> 观察还没迁移时的失败
-> alembic upgrade head
-> 观察表和字段创建
-> 写入业务数据
-> alembic downgrade 202607290001
-> 观察代码和数据库版本不匹配
-> alembic upgrade head
-> 恢复正常
```

这条链路就是正式项目数据库迁移的最小版本。

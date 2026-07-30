# Alembic 零基础入门

这份文档放在命令和代码之前读。

如果你已经学完 SQLAlchemy 和 PostgreSQL，你现在知道：

```text
Python ORM Model 可以描述表结构
DATABASE_URL 可以切换数据库
```

但真实项目还差一个关键问题：

```text
表结构以后变了，怎么安全地改数据库？
```

这就是 Alembic 要解决的问题。

## 为什么不能一直用 create_all

`create_all` 的作用是：

```text
根据当前 ORM Model，创建还不存在的表
```

它适合学习阶段，但正式项目有明显问题。

### 问题一：它不记录版本

真实项目需要知道：

```text
当前数据库结构是第几版
线上数据库执行过哪些变更
本地数据库和线上数据库是否一致
```

`create_all` 不擅长回答这些问题。

Alembic 会用 `alembic_version` 表记录当前版本。

### 问题二：它不擅长改已有表

例如你上线后已经有了 `knowledge_articles` 表和很多数据。

后来你想新增：

```text
status
```

如果只是修改 ORM Model，数据库里的旧表不会自动安全变更。

你需要一份明确迁移：

```text
给 knowledge_articles 增加 status 字段
给旧数据补默认值 draft
必要时创建索引
```

### 问题三：它不表达回滚方案

真实项目变更可能失败。

你需要知道怎么从新版本退回旧版本。

Alembic 迁移文件里有两个函数：

```python
def upgrade() -> None:
    ...

def downgrade() -> None:
    ...
```

`upgrade` 表示升级。

`downgrade` 表示回滚。

## Alembic 的核心概念

### revision

每个迁移文件都有一个版本号，叫 revision。

本模块有两个：

```text
202607290001
202607290002
```

可以理解成数据库结构版本号。

### down_revision

`down_revision` 表示上一个版本。

例如：

```python
revision = "202607290002"
down_revision = "202607290001"
```

意思是：

```text
第二个迁移必须接在第一个迁移后面执行
```

### head

`head` 表示当前迁移链的最新版本。

执行：

```powershell
python -m alembic upgrade head
```

意思是：

```text
把数据库升级到最新结构版本
```

### alembic_version 表

执行迁移后，数据库里会出现一张表：

```text
alembic_version
```

它不是业务表，而是 Alembic 自己用来记录当前版本的表。

本模块的接口：

```text
GET /migration/status
```

会读取这张表。

## 本模块的迁移链

第一个迁移：

```text
202607290001_create_knowledge_articles.py
```

作用：

```text
创建 knowledge_articles 表
```

第二个迁移：

```text
202607290002_add_article_status.py
```

作用：

```text
给 knowledge_articles 表增加 status 字段
```

这模拟真实项目：

```text
第一版上线：文章只有 title 和 content
第二版上线：文章需要草稿、发布、归档状态
```

## 为什么新增非空字段要小心

假设表里已经有旧数据：

| id | title | content |
| --- | --- | --- |
| 1 | 第一篇 | 内容 |

现在你要新增：

```text
status NOT NULL
```

旧数据没有 status。

如果不给默认值，数据库会不知道旧数据的 status 应该是什么。

所以本模块迁移里写了：

```python
server_default="draft"
```

意思是：

```text
旧数据和未显式提供 status 的新数据，默认都是 draft
```

这就是一个真实工程判断，而不是机械加字段。

## 最常用命令

查看迁移历史：

```powershell
python -m alembic history
```

查看当前数据库版本：

```powershell
python -m alembic current
```

升级到最新版本：

```powershell
python -m alembic upgrade head
```

回滚一个版本：

```powershell
python -m alembic downgrade -1
```

回滚到指定版本：

```powershell
python -m alembic downgrade 202607290001
```

生成新迁移文件：

```powershell
python -m alembic revision --autogenerate -m "add reviewed_at to articles"
```

注意：自动生成迁移后必须人工检查迁移文件。

Alembic 能帮你发现很多结构差异，但不能替你判断业务含义和数据风险。

## 你要掌握的核心链路

```text
修改 models.py
-> 生成迁移文件
-> 检查 upgrade / downgrade
-> alembic upgrade head
-> 数据库结构变化
-> FastAPI 接口使用新结构
```

学完本模块，你应该能回答：

- `create_all` 和 Alembic 的区别。
- `upgrade` 和 `downgrade` 分别做什么。
- `alembic_version` 表有什么用。
- 为什么新增非空字段要考虑旧数据。
- 为什么代码版本和数据库版本必须一起发布。

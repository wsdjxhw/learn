# Alembic 数据库迁移

这一节的目标：学会正式项目里如何管理数据库表结构变化。

前面模块用过：

```python
Base.metadata.create_all(bind=engine)
```

它适合学习阶段快速建表，但正式项目不能只靠它。真实项目需要知道：

```text
数据库现在是哪个结构版本
这次结构改了什么
怎么升级
怎么回滚
旧数据会不会坏
```

Alembic 就是 SQLAlchemy 项目里常用的数据库迁移工具。

## 先读

如果你第一次接触数据库迁移，先读：

[ALEMBIC_BASICS.md](ALEMBIC_BASICS.md)

再看代码讲解：

[ALEMBIC_EXPLAINED.md](ALEMBIC_EXPLAINED.md)

迁移脚本命名规则：

[MIGRATION_NAMING.md](MIGRATION_NAMING.md)

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\07_alembic_migrations
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置：

```powershell
Copy-Item .env.example .env
```

先启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开：

```text
http://127.0.0.1:8000/docs
```

注意：本模块启动时不会自动建表。服务能启动，只表示 FastAPI 进程正常，不表示数据库结构已经准备好。

## 第一次观察

先在 `/docs` 里调用：

1. `GET /health`
2. `GET /db/health`
3. `GET /migration/status`
4. `GET /db/tables`
5. `GET /articles`

如果还没有执行迁移，`GET /articles` 应该会失败，并提示你执行：

```powershell
python -m alembic upgrade head
```

这不是坏事。它是在暴露真实工程问题：

```text
代码启动了，不代表数据库表结构已经升级。
```

## 执行迁移

在模块目录里执行：

```powershell
python -m alembic history
```

你会看到两个迁移版本：

```text
202607290001 -> 创建 knowledge_articles 表
202607290002 -> 给 knowledge_articles 增加 status 字段
```

升级到最新版本：

```powershell
python -m alembic upgrade head
```

查看当前数据库版本：

```powershell
python -m alembic current
```

再回到 `/docs` 测试：

1. `GET /migration/status`
2. `GET /db/tables`
3. `POST /articles`
4. `GET /articles`
5. `PATCH /articles/{article_id}/status`

## 创建文章示例

请求体：

```json
{
  "title": "为什么需要 Alembic",
  "content": "create_all 不能清楚记录每一次表结构变更，Alembic 可以把变更写成版本化迁移文件。",
  "status": "draft"
}
```

更新状态：

```json
{
  "status": "published"
}
```

允许的状态：

```text
draft
published
archived
```

## 观察回滚

先确认已经有数据，然后回滚到第一个迁移版本：

```powershell
python -m alembic downgrade 202607290001
```

再调用：

```text
GET /migration/status
GET /db/tables
GET /articles
```

你会看到：

- `current_version` 变成 `202607290001`。
- `knowledge_articles` 表还在。
- `status` 字段不见了。
- 当前 Python 代码查询 `status` 时会失败。

这说明一个重要事实：

```text
代码版本和数据库版本必须匹配。
```

恢复到最新版本：

```powershell
python -m alembic upgrade head
```

## 本课练习

1. 不执行迁移直接调用 `GET /articles`，记录错误和 hint，解释为什么服务启动不等于表结构可用。
2. 执行 `python -m alembic upgrade head`，再创建一条文章，确认 `/migration/status`、`/db/tables`、`/articles` 三处结果互相对应。
3. 回滚到 `202607290001`，观察 `status` 字段消失后当前代码为什么会报错，再升级回 `head` 验证恢复。
4. 阅读 `202607290002_add_article_status.py`，说明为什么给已有表新增非空字段时需要默认值。
5. 设计一个新的迁移：给文章增加 `reviewed_at` 字段。要求你先判断它应不应该允许为空，并说明对旧数据的影响，再生成迁移文件。

这些练习的目标不是机械加字段，而是理解真实项目里的数据库结构版本、旧数据兼容、回滚风险和代码/数据库版本匹配。

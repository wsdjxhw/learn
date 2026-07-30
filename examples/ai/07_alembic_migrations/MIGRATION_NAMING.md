# 迁移脚本命名规则

本模块约定 Alembic 迁移版本号使用这种格式：

```text
YYYYMMDDNNNN
```

示例：

```text
202607290001_create_knowledge_articles.py
202607290002_add_article_status.py
202607290003_add_reviewed_at_to_articles.py
```

## 为什么自动生成的名字不一样

如果直接执行：

```powershell
python -m alembic revision --autogenerate -m "add reviewed_at to articles"
```

Alembic 默认会生成类似这样的随机版本号：

```text
1407f94b6a41_add_reviewed_at_to_articles.py
```

这不是 bug，而是 Alembic 默认行为。

## 项目里的正确生成方式

以后生成新迁移时，显式传入 `--rev-id`：

```powershell
python -m alembic revision --autogenerate --rev-id 202607290003 -m "add reviewed_at to articles"
```

下一个迁移就用：

```text
202607290004
```

## 生成后必须人工检查

`--autogenerate` 只是“根据当前 Model 和数据库差异猜测迁移内容”，不能直接无脑执行。

生成后必须检查：

- `revision` 是否符合项目格式。
- `down_revision` 是否指向上一个版本。
- `upgrade()` 是否只包含本次想做的变更。
- `downgrade()` 是否只回滚本次变更。
- 有没有误生成 `drop_table()`、`drop_column()`、`drop_index()`。

如果看到和本次目标无关的删除操作，先不要执行 `upgrade`。

## 本次案例

自动生成脚本时曾出现两个危险操作：

```python
op.drop_table("database_notes")
op.drop_index(..., table_name="knowledge_articles")
```

但本次目标只是新增：

```text
knowledge_articles.reviewed_at
```

所以最终迁移文件应该只保留：

```python
op.add_column("knowledge_articles", ...)
```

回滚时也只删除：

```python
op.drop_column("knowledge_articles", "reviewed_at")
```

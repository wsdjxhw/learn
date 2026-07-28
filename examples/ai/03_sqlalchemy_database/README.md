# SQLAlchemy 和数据库连接

这一节的目标：把上一节手写 `sqlite3` 的数据层，升级成 SQLAlchemy ORM。

你要理解的变化：

```text
上一节：直接写 SQL
这一节：用 Python class 映射数据库表
```

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\03_sqlalchemy_database
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开：

```text
http://127.0.0.1:8000/docs
```

## 当前默认数据库

默认使用 SQLite：

```text
DATABASE_URL=sqlite:///./chat_sqlalchemy.db
```

第一次启动时会自动生成：

```text
chat_sqlalchemy.db
```

这个文件是本地数据库文件，不需要手动创建。

## 后续切 PostgreSQL

以后安装 PostgreSQL 后，把 `.env` 里的 `DATABASE_URL` 改成类似：

```text
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/ai_learn
```

这就是为什么现在要先学 `DATABASE_URL`。

## 文件分工

`database.py`

负责数据库连接、建表、创建数据库会话。

`models.py`

负责 ORM 模型。可以类比 Java 里的 Entity。

`schemas.py`

负责请求和响应 DTO。可以类比 Java 里的 Request / Response DTO。

`main.py`

负责 FastAPI 接口。可以类比 Java Controller。

`provider.py`

负责 mock 或 DeepSeek 回复。

## 测试顺序

1. `GET /health`
2. `POST /sessions`
3. `GET /sessions`
4. `POST /sessions/{session_id}/chat`
5. `GET /sessions/{session_id}/messages`
6. `GET /stats`

## 本课练习

1. 给 `ChatSession` 增加一个 `description` 字段。
2. 给 `GET /sessions` 增加 `keyword` 查询参数，按标题搜索。
3. 给 `GET /stats` 增加 `user_message_count` 和 `assistant_message_count`。
4. 对比 `02_chat_history/db.py` 和本节的 `models.py`、`database.py`，说明两种写法的区别。

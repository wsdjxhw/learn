# PostgreSQL 实战连接

这一节的目标：把前面学过的 SQLAlchemy，从本地 SQLite 切到真正的 PostgreSQL。

你要理解的不是“换一个数据库名字”，而是这条真实链路：

```text
.env 里的 DATABASE_URL
-> SQLAlchemy engine
-> 数据库连接健康检查
-> 创建表
-> 写入一条数据
-> 确认数据真的落在当前数据库
```

## 零基础先读

如果你之前没学过 PostgreSQL，先读：

[POSTGRESQL_BASICS.md](POSTGRESQL_BASICS.md)

这份文档先讲 PostgreSQL 服务、端口、账号、数据库、schema、表、SQL、`DATABASE_URL`，再进入本模块代码。

如果你电脑上还没有安装 PostgreSQL，再读：

[POSTGRESQL_INSTALL_WINDOWS.md](POSTGRESQL_INSTALL_WINDOWS.md)

这份文档按 Windows 环境说明下载安装、确认服务启动、创建 `ai_learn` 数据库、配置 `.env` 和排查常见连接错误。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\06_postgresql_setup
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置文件：

```powershell
Copy-Item .env.example .env
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

## 如果启动时报端口或 socket 错误

如果你看到类似：

```text
[WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试
```

或者提示端口已经被占用，先确认是不是旧的 `uvicorn` 还在运行。

查看 `8000` 端口：

```powershell
netstat -ano | Select-String ':8000'
```

如果看到类似：

```text
TCP    127.0.0.1:8000    0.0.0.0:0    LISTENING    19144
```

最后一列 `19144` 是进程 ID。确认这是你之前启动的 Python / uvicorn 后，可以停止它：

```powershell
Stop-Process -Id 19144
```

也可以不停止旧服务，直接换端口启动：

```powershell
python -m uvicorn main:app --reload --port 9001
```

注意不要把 FastAPI 启动在 PostgreSQL 的端口 `5432` 上。`5432` 是数据库服务端口，FastAPI 通常用 `8000`、`9001` 这类 Web API 端口。

## 默认模式

默认 `.env.example` 使用 SQLite：

```text
DATABASE_URL=sqlite:///./postgresql_setup.db
```

这样做是为了先保证服务能启动、接口能跑通。

跑通 SQLite 后，再把 `.env` 改成 PostgreSQL：

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_learn
```

其中：

- `postgresql+psycopg`：数据库类型和 Python 驱动。
- `postgres:postgres`：用户名和密码。
- `localhost:5432`：PostgreSQL 服务地址和端口。
- `ai_learn`：数据库名，需要提前创建。

## 测试顺序

先用默认 SQLite 跑一遍：

1. `GET /health`
2. `GET /db/health`
3. `GET /db/tables`
4. `POST /notes`
5. `GET /notes`

然后切到 PostgreSQL：

1. 确认 PostgreSQL 服务已启动。
2. 创建数据库，例如 `ai_learn`。
3. 修改 `.env` 里的 `DATABASE_URL`。
4. 重启 `uvicorn`。
5. `GET /db/health`
6. `POST /setup/create-tables`
7. `POST /notes`
8. `GET /notes`
9. `GET /db/tables`

## 创建笔记示例

请求体：

```json
{
  "title": "postgres-check",
  "content": "这条数据用于验证当前 DATABASE_URL 指向的数据库能写入和读取。"
}
```

返回里重点看：

- `id` 是否生成。
- `created_at` 是否由数据库生成。
- `GET /notes` 里的 `database_kind` 是 `sqlite` 还是 `postgresql`。
- `GET /db/health` 里的 `current_database` 是否是你创建的 PostgreSQL 数据库。

## 本课练习

1. 先不安装 PostgreSQL，用默认 SQLite 跑通完整测试顺序，确认 `postgresql_setup.db` 文件被创建。
2. 故意把 PostgreSQL 密码或端口写错，调用 `GET /db/health`，记录 `error_type`、`error` 和 `hint`，说明它们分别帮助你判断什么问题。
3. 创建一个真实 PostgreSQL 数据库，把 `.env` 切到 PostgreSQL，调用 `POST /setup/create-tables`，再创建一条 note，确认 `GET /notes` 返回的 `database_kind` 是 `postgresql`。
4. 对比 SQLite 和 PostgreSQL 两次 `GET /db/health` 的返回，说明 `database_url`、`driver`、`tables`、`current_database` 有什么不同。
5. 思考题：现在 `POST /setup/create-tables` 可以创建表，为什么正式项目仍然需要下一模块的 Alembic？请从“表结构变更”和“生产数据不能丢”两个角度回答。

这些练习都对应真实开发能力：连接排错、环境配置、确认数据落库、识别当前数据库，以及理解为什么需要迁移工具。

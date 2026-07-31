# Docker 部署配置讲解

这一份文档按文件解释 `deploy/docker` 模块。

## 目录结构

```text
deploy/docker
├── Dockerfile
├── Dockerfile.dockerignore
├── docker-compose.yml
├── .env.example
├── README.md
├── DOCKER_BASICS.md
└── DOCKER_DEPLOY_EXPLAINED.md
```

这些文件的分工：

- `Dockerfile`：说明如何把 `chat_ui` 构建成镜像。
- `Dockerfile.dockerignore`：说明构建镜像时哪些文件不要发送给 Docker。
- `docker-compose.yml`：说明如何同时启动应用容器和 PostgreSQL 容器。
- `.env.example`：给出运行时配置模板。
- `README.md`：告诉你怎么启动、怎么测试、怎么练习。
- `DOCKER_BASICS.md`：解释 Docker 基础概念。

## Dockerfile

第一行：

```dockerfile
FROM python:3.13-slim
```

表示镜像从 Python 3.13 的精简 Linux 环境开始。

`WORKDIR /app` 表示后续命令默认在 `/app` 下执行。它类似你在 PowerShell 里先执行：

```powershell
cd C:\some\folder
```

依赖安装分成两步：

```dockerfile
COPY examples/frontend/chat_ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
```

这样做是为了利用 Docker 缓存。只要 `requirements.txt` 没变，下一次构建就不用重复安装依赖。

复制应用代码：

```dockerfile
COPY examples/frontend/chat_ui /app/examples/frontend/chat_ui
```

这一步把前端聊天模块放进容器。

生产启动命令：

```dockerfile
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

这里不使用 `--reload`。`--reload` 是开发模式，会监控文件变化并重启服务；生产容器更强调稳定运行。

`--host 0.0.0.0` 很重要。容器里如果只监听 `127.0.0.1`，宿主机端口映射后也可能访问不到服务。

## Dockerfile.dockerignore

构建镜像时，Docker 会先把构建上下文发送给 Docker daemon。

如果不忽略文件，`.venv`、`.git`、数据库文件、`.env` 都可能被发送过去。

本模块忽略这些内容：

```text
.git
.venv
__pycache__
*.db
.env
```

这有两个目的：

- 构建更快。
- 避免把本地密钥和数据库文件打进镜像。

## docker-compose.yml 的 app 服务

`app` 服务负责运行 FastAPI：

```yaml
build:
  context: ../..
  dockerfile: deploy/docker/Dockerfile
```

`context: ../..` 表示构建上下文是仓库根目录。因为 Dockerfile 要复制：

```text
examples/frontend/chat_ui
```

如果 context 只设成 `deploy/docker`，Dockerfile 就看不到 `examples` 目录。

端口映射：

```yaml
ports:
  - "${APP_PORT:-8000}:8000"
```

左边来自 `.env`，右边是容器内部端口。

数据持久化：

```yaml
CHAT_DB_PATH: /app/data/chat_ui.db
volumes:
  - chat_ui_data:/app/data
```

这两行要一起看：

- `CHAT_DB_PATH` 告诉 Python 代码把 SQLite 文件写到 `/app/data/chat_ui.db`。
- `chat_ui_data:/app/data` 告诉 Docker 把 `/app/data` 保存到命名数据卷。

如果只配置环境变量，不配置 volume，容器删除后数据仍然会丢。

## docker-compose.yml 的 postgres 服务

`postgres` 服务负责启动数据库：

```yaml
image: postgres:16
```

这表示直接使用官方 PostgreSQL 镜像，不需要自己写数据库 Dockerfile。

数据库初始化配置：

```yaml
POSTGRES_DB: ${POSTGRES_DB:-ai_learn}
POSTGRES_USER: ${POSTGRES_USER:-ai_user}
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-ai_password}
```

这些值来自 `.env`。如果 `.env` 没写，就使用冒号后面的默认值。

PostgreSQL 数据卷：

```yaml
postgres_data:/var/lib/postgresql/data
```

PostgreSQL 的真实数据文件保存在 `/var/lib/postgresql/data`。把这个目录挂到数据卷后，数据库容器重建时数据不会立刻丢失。

端口映射默认是：

```yaml
5433:5432
```

这是为了避开你本机可能已经安装的 PostgreSQL `5432`。左边 `5433` 是宿主机端口，右边 `5432` 是容器内部端口。

## 健康检查

`app` 的健康检查访问：

```text
http://127.0.0.1:8000/health
```

这里的 `127.0.0.1` 是容器内部的地址，不是宿主机地址。

`postgres` 的健康检查使用：

```text
pg_isready
```

如果 `postgres` 还没准备好，Compose 会等待它变成 healthy，再启动依赖它的服务。

## .env.example

`.env.example` 是模板，不保存真实密钥。

你复制成 `.env` 后，本地可以按需修改。

当前 `DEEPSEEK_API_KEY` 是占位值，所以 `provider.py` 会走 mock 模式。这样没有真实 key 也能完整跑通部署流程。

## 本模块的关键边界

这里有一个真实项目里很常见的判断点：

```text
启动了 PostgreSQL 容器
不等于
应用已经使用 PostgreSQL
```

应用是否使用 PostgreSQL，取决于应用代码有没有读取 PostgreSQL 的连接配置，并通过数据库驱动连接它。

当前 `chat_ui` 的数据库访问层是 `sqlite3`，所以它仍然使用 SQLite。Compose 里的 PostgreSQL 是为下一步存储替换做准备。

这个边界必须分清，否则你可能看到 PostgreSQL 容器 healthy，就误以为数据已经写进 PostgreSQL。

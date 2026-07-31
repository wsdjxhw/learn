# Docker 基础知识

这一份文档只讲本模块必须理解的 Docker 概念。

## Docker 解决什么问题

本地启动 FastAPI 时，你依赖的是自己电脑上的 Python、pip 包、`.env` 文件和启动命令。

部署到服务器时，如果服务器环境和你电脑不一样，就容易出现这些问题：

- Python 版本不一致。
- 依赖没装全。
- 启动命令写错。
- 环境变量缺失。
- 数据文件放错位置。

Docker 的作用是把“运行环境”和“应用代码”打包到一个镜像里。服务器只要能运行 Docker，就能按同一套方式启动应用。

## 镜像和容器

镜像 image 可以类比成 Java 里的可发布产物，比如一个已经打好的 jar 加上运行环境说明。

容器 container 是镜像运行起来之后的进程。

简单理解：

```text
Dockerfile 构建出 image
image 运行起来变成 container
container 里启动 uvicorn
uvicorn 对外提供 FastAPI 服务
```

## Dockerfile

Dockerfile 是构建镜像的说明书。

本模块的 Dockerfile 主要做四件事：

1. 从 `python:3.13-slim` 这个基础镜像开始。
2. 复制 `requirements.txt`。
3. 安装 FastAPI、uvicorn、python-dotenv、openai。
4. 复制 `chat_ui` 代码并启动 `uvicorn`。

为什么先复制 `requirements.txt`，再复制代码？

因为 Docker 构建有缓存。依赖不变时，`pip install` 这一层可以复用；你只改业务代码时，构建会更快。

## docker compose

一个真实应用通常不止一个容器。

本模块有：

- `app`：FastAPI + 静态前端页面。
- `postgres`：PostgreSQL 数据库服务。

`docker-compose.yml` 的作用是把多个容器的启动方式写在一个文件里，避免你手动输入很多 `docker run` 命令。

## 端口映射

容器里的 `uvicorn` 监听 `8000` 端口，但这个端口默认只在容器内部可见。

Compose 里的配置：

```yaml
ports:
  - "${APP_PORT:-8000}:8000"
```

含义是：

```text
宿主机 APP_PORT -> 容器 8000
```

如果 `APP_PORT=9000`，你访问的是：

```text
http://127.0.0.1:9000/
```

但容器内部仍然是 `8000`。

## 环境变量

环境变量可以理解成“运行时配置”。

同一份镜像不应该因为端口、标题、API Key 不同就重新改代码。应该通过 `.env` 控制。

本模块里的 `.env.example` 包含：

- `APP_PORT`
- `APP_TITLE`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`

注意：真实 `.env` 不应该提交到 Git。项目根目录 `.gitignore` 已经忽略了 `.env`。

## 数据卷

容器默认是可以删除重建的。

如果 SQLite 数据库文件只放在容器内部，容器删掉后聊天历史也会丢。

本模块用：

```yaml
volumes:
  - chat_ui_data:/app/data
```

再配合：

```yaml
CHAT_DB_PATH: /app/data/chat_ui.db
```

让 SQLite 数据库文件保存在 Docker 数据卷里。

这就是“容器可以重建，数据要单独保存”的基本思路。

## 健康检查

容器进程存在，不等于应用真的可用。

比如 Python 进程启动了，但数据库还连不上，或者 Web 服务没有正常响应。

健康检查就是定期访问一个轻量接口：

```text
GET /health
```

如果接口正常返回，Docker 会把容器标记为 `healthy`。

## PostgreSQL 容器

PostgreSQL 容器提供一个独立数据库服务。

它有自己的：

- 数据库名：`POSTGRES_DB`
- 用户名：`POSTGRES_USER`
- 密码：`POSTGRES_PASSWORD`
- 容器内部端口：`5432`
- 宿主机默认映射端口：`5433`
- 数据卷：`postgres_data`

当前 `chat_ui` 仍使用 SQLite，所以 PostgreSQL 只是先作为部署练习对象启动。后续要让应用真正使用 PostgreSQL，还需要应用代码读取 `DATABASE_URL`，并把 SQLite 访问层替换为 SQLAlchemy / PostgreSQL 访问层。

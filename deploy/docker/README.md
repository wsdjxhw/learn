# Docker 和部署

这一节的目标：把已经完成的 `examples/frontend/chat_ui` 打包成可以用 Docker 启动的服务，并理解部署时最常见的几个对象：

```text
Dockerfile
-> 镜像 image
-> 容器 container
-> 环境变量 .env
-> 数据卷 volume
-> 健康检查 healthcheck
-> docker compose 编排
```

本模块不是直接上复杂云平台，而是先把“本地能跑的 FastAPI 应用”变成“容器里也能跑的应用”。

## 先读

基础知识：

[DOCKER_BASICS.md](DOCKER_BASICS.md)

代码和配置讲解：

[DOCKER_DEPLOY_EXPLAINED.md](DOCKER_DEPLOY_EXPLAINED.md)

## 本模块会启动什么

`docker-compose.yml` 会启动两个服务：

- `app`：打包后的 `examples/frontend/chat_ui`，对外暴露 Web 页面和 API。
- `postgres`：PostgreSQL 容器，用来学习数据库容器、账号密码、端口和健康检查。

当前边界要说清楚：`chat_ui` 代码现在仍然使用 SQLite。Compose 里的 PostgreSQL 已经搭好，但还没有接入 `chat_ui` 的 ORM 存储层。这样安排是为了先学部署框架，再在后续模块学习把应用存储切到 PostgreSQL。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\deploy\docker
```

复制配置：

```powershell
Copy-Item .env.example .env
```

构建并启动：

```powershell
docker compose up --build
```

后台启动：

```powershell
docker compose up --build -d
```

查看服务状态：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f app
```

停止服务：

```powershell
docker compose down
```

如果你想连数据卷一起删除，才使用：

```powershell
docker compose down -v
```

`-v` 会删除 SQLite 数据卷和 PostgreSQL 数据卷，聊天历史和数据库数据都会丢。

## 打开页面

浏览器打开：

```text
http://127.0.0.1:8000/
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

健康检查：

```text
http://127.0.0.1:8000/health
```

如果 `.env` 里把 `APP_PORT` 改成 `9000`，对应地址就是：

```text
http://127.0.0.1:9000/
```

## 接口测试顺序

1. 打开 `GET /health`，确认应用容器启动成功。
2. 打开 `/`，确认静态前端页面能加载。
3. 调用 `GET /api/sessions`，确认默认会话已创建。
4. 调用 `POST /api/sessions/{session_id}/messages`，发送一条消息。
5. 调用 `GET /api/tasks/{task_id}`，观察任务状态。
6. 打开页面发送消息，观察 SSE 状态和 sources 展示。
7. 执行 `docker compose restart app`，再次打开页面，确认 SQLite 数据卷里的聊天历史还在。
8. 执行 `docker compose ps`，观察 `app` 和 `postgres` 的健康状态。

## 本课练习

1. 把 `.env` 里的 `APP_PORT` 改成 `9000`，重新启动，说明宿主机端口和容器端口的区别。
2. 发送一条消息后执行 `docker compose restart app`，确认消息是否还在，并解释 `chat_ui_data` 数据卷解决了什么问题。
3. 观察 `docker compose ps` 里的 `postgres` 健康状态，再说明为什么宿主机默认用 `5433`，但容器内部仍然是 `5432`。
4. 阅读 `Dockerfile`，画出“复制依赖文件 -> 安装依赖 -> 复制代码 -> 启动 uvicorn”的构建链路。
5. 对比本地启动命令 `python -m uvicorn main:app --reload` 和 Dockerfile 里的生产启动命令，说明为什么容器里不使用 `--reload`。
6. 思考题：现在 app 使用 SQLite，compose 里也启动了 PostgreSQL。请说明这为什么还不等于“应用已经使用 PostgreSQL”，以及后续代码需要补哪类配置。

这些练习对应真实部署能力：端口映射、环境变量、持久化、健康检查、日志查看和识别“容器存在”与“应用真正使用它”的区别。

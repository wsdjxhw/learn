# syntax=docker/dockerfile:1

# 这个 Dockerfile 用来打包 examples/frontend/chat_ui。
# Dockerfile 可以类比成“服务器构建说明书”：从什么基础环境开始，复制哪些文件，安装哪些依赖，最后用什么命令启动服务。
FROM python:3.13-slim

# PYTHONDONTWRITEBYTECODE=1：不在容器里生成 __pycache__。
# PYTHONUNBUFFERED=1：让 print / 日志尽快输出，docker logs 能更及时看到内容。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# WORKDIR 类似进入目录。后续 COPY、RUN、CMD 如果使用相对路径，都会以这个目录为基准。
WORKDIR /app

# 先复制 requirements.txt，再安装依赖。
# 这样只要依赖文件没变，Docker 可以复用缓存；改 Python 代码时不用每次重新下载依赖。
COPY examples/frontend/chat_ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 复制真正要运行的应用代码。
# 当前部署模块选择 chat_ui 作为目标，是因为它已经包含 FastAPI 接口和静态前端页面。
COPY examples/frontend/chat_ui /app/examples/frontend/chat_ui

WORKDIR /app/examples/frontend/chat_ui

# EXPOSE 是给读 Dockerfile 的人看的端口说明。
# 真正把端口映射到宿主机，是 docker-compose.yml 里的 ports 负责。
EXPOSE 8000

# HEALTHCHECK 会在容器内部访问 /health。
# 生产部署里，编排系统通常会用健康检查判断服务是否真的启动成功。
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"

# 生产启动命令和本地开发的 --reload 不同：
# - --host 0.0.0.0 让容器外部可以访问服务。
# - 不加 --reload，避免生产环境因为文件扫描带来额外开销和不稳定行为。
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

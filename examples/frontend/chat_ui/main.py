import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import (
    create_chat_task,
    create_message,
    create_session,
    ensure_default_session,
    get_session,
    get_task,
    init_db,
    list_messages,
    list_sessions,
    update_session_title,
)
from provider import get_deepseek_model, get_provider_name
from worker import process_chat_task

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

load_dotenv(dotenv_path=BASE_DIR / ".env")

app = FastAPI(title=os.getenv("APP_TITLE", "AI Chat UI"))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SessionCreate(BaseModel):
    # 请求 DTO：新建会话时，前端只需要传 title。
    # 类比 Java 里的 CreateSessionRequest。
    title: str = "新会话"


class SessionUpdate(BaseModel):
    # PATCH /api/sessions/{session_id} 的请求体。
    # 这里用单独 DTO，是为了让“创建”和“更新”的输入边界更清楚。
    title: str


class MessageCreate(BaseModel):
    # 请求 DTO：前端发送用户消息时传 message。
    # 后端会先保存 user 消息，再创建后台任务生成 assistant 消息。
    message: str


@app.on_event("startup")
def startup() -> None:
    init_db()
    ensure_default_session()


@app.get("/")
def index() -> FileResponse:
    # 返回静态首页。前端页面再通过 /api/* 接口读取会话和消息。
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "storage": "sqlite",
        "provider": get_provider_name(),
        "model": get_deepseek_model(),
    }


@app.get("/api/sessions")
def get_sessions() -> dict:
    return {"items": list_sessions()}


@app.post("/api/sessions")
def post_session(payload: SessionCreate) -> dict:
    title = payload.title.strip() or "新会话"
    return create_session(title=title)


@app.patch("/api/sessions/{session_id}")
def patch_session(session_id: int, payload: SessionUpdate) -> dict:
    # session_id 来自路径参数。
    # payload.title 来自 JSON 请求体。
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title must not be empty")

    session = update_session_title(session_id=session_id, title=title)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: int) -> dict:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"items": list_messages(session_id)}


@app.post("/api/sessions/{session_id}/messages")
def post_session_message(
    session_id: int,
    payload: MessageCreate,
    background_tasks: BackgroundTasks,
) -> dict:
    # 这是前端发送消息的核心接口：
    # 1. 保存 user 消息。
    # 2. 创建 chat_task。
    # 3. 用 BackgroundTasks 后台生成 assistant 消息。
    # 4. 立刻把 task_id 返回给前端。
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must not be empty")

    user_message = create_message(session_id=session_id, role="user", content=message)
    task = create_chat_task(session_id=session_id, user_message=message)
    background_tasks.add_task(
        process_chat_task,
        task["id"],
        session_id,
        message,
    )
    return {
        "user_message": user_message,
        "task": task,
        "task_url": f"/api/tasks/{task['id']}",
    }


@app.get("/api/tasks/{task_id}")
def get_chat_task(task_id: int) -> dict:
    # 前端通过这个接口轮询后台任务状态。
    # 成功后 task 里会带 sources，页面右侧面板会展示这些来源。
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

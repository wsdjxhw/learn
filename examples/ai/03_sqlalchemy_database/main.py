from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import create_tables, get_db, get_database_url
from models import ChatMessage, ChatSession
from provider import generate_reply, get_model_name, get_provider_name
from schemas import ChatRequest, MessageRead, SessionCreate, SessionRead

app = FastAPI(title="AI Chat With SQLAlchemy")


@app.on_event("startup")
def startup() -> None:
    # 服务启动时根据 ORM 模型创建数据库表。
    create_tables()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
        "database_url": get_database_url(),
    }


@app.post("/sessions", response_model=SessionRead)
def create_chat_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
) -> ChatSession:
    # 新建 ORM 对象，然后交给 SQLAlchemy 保存。
    session = ChatSession(title=payload.title, description=payload.description)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.get("/sessions")
def list_chat_sessions(
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    # keyword 是查询参数，用于按标题搜索会话。
    statement = select(ChatSession).order_by(ChatSession.id.desc())
    if keyword:
        statement = statement.where(ChatSession.title.contains(keyword))

    sessions = db.scalars(statement).all()
    return {"items": sessions}


@app.get("/sessions/{session_id}/messages")
def list_chat_messages(
    session_id: int,
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
    )
    messages = db.scalars(statement).all()
    return {"items": messages}


@app.post("/sessions/{session_id}/chat")
def chat(
    session_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=payload.message,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    history_statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
    )
    history_messages = db.scalars(history_statement).all()
    model_messages = [
        {"role": "system", "content": payload.system_prompt},
        *[
            {"role": message.role, "content": message.content}
            for message in history_messages
        ],
    ]

    reply_text = generate_reply(model_messages)
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=reply_text,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return {
        "session_id": session_id,
        "user_message": MessageRead.model_validate(user_message),
        "assistant_message": MessageRead.model_validate(assistant_message),
        "provider": get_provider_name(),
        "model": get_model_name(),
    }


@app.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    # 统计会话数量和消息数量，练习 SQLAlchemy 的聚合查询。
    session_count = db.scalar(select(func.count(ChatSession.id)))
    message_count = db.scalar(select(func.count(ChatMessage.id)))
    user_message_count = db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.role == "user"))
    assistant_message_count = db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.role == "assistant"))
    return {
        "session_count": session_count,
        "message_count": message_count,
        "user_message_count": user_message_count,
        "assistant_message_count": assistant_message_count,
    }

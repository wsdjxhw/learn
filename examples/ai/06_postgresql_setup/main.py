from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import (
    check_connection,
    create_tables,
    get_database_kind,
    get_db,
    get_safe_database_url,
    list_table_names,
)
from models import DatabaseNote
from schemas import DatabaseNoteCreate, DatabaseNoteRead

app = FastAPI(title="PostgreSQL Setup Practice")

# 记录启动阶段建表是否失败。
# 这样即使 PostgreSQL 配错了，FastAPI 服务仍能启动，学习者可以打开 /docs 看错误。
startup_database_error: str | None = None


@app.on_event("startup")
def startup() -> None:
    global startup_database_error
    try:
        # 默认 SQLite 下会自动建表，保证“先能运行”。
        # 如果你把 DATABASE_URL 改成 PostgreSQL 但账号、库名或端口有问题，
        # 这里会失败；失败信息会在 /health 和 /db/health 里展示。
        create_tables()
        startup_database_error = None
    except SQLAlchemyError as exc:
        startup_database_error = str(exc)


@app.get("/health")
def health() -> dict:
    # 普通健康检查：确认 FastAPI 服务本身启动了。
    # database_startup_ok 只说明启动建表是否成功，不等于业务写入一定成功。
    return {
        "status": "ok",
        "database_kind": get_database_kind(),
        "database_url": get_safe_database_url(),
        "database_startup_ok": startup_database_error is None,
        "database_startup_error": startup_database_error,
    }


@app.get("/db/health")
def database_health() -> dict:
    # 数据库健康检查：真正打开连接并执行 SELECT 1。
    # 它能暴露真实工程问题，例如密码错、库不存在、服务没启动。
    return check_connection()


@app.post("/setup/create-tables")
def setup_create_tables() -> dict:
    # 这个接口用于手动创建表。
    # 典型场景：你刚把 .env 从 SQLite 改成 PostgreSQL，然后重启服务验证连接。
    #
    # 注意：这是学习模块里的简化做法。
    # 正式项目应该用 Alembic 管理迁移，下一模块会专门学习。
    try:
        create_tables()
        return {
            "ok": True,
            "database_kind": get_database_kind(),
            "database_url": get_safe_database_url(),
            "tables": list_table_names(),
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/db/tables")
def database_tables() -> dict:
    # 查看当前数据库中的表。
    # 这个接口可以帮助你确认：现在操作的是 SQLite 文件，还是 PostgreSQL 数据库。
    try:
        return {
            "database_kind": get_database_kind(),
            "database_url": get_safe_database_url(),
            "items": list_table_names(),
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/notes", response_model=DatabaseNoteRead)
def create_note(
    payload: DatabaseNoteCreate,
    db: Session = Depends(get_db),
) -> DatabaseNote:
    # payload 来自请求体 JSON，FastAPI 根据 DatabaseNoteCreate 自动校验。
    # db 来自 Depends(get_db)，可以理解成 FastAPI 自动注入数据库会话。
    #
    # 这个接口的学习价值不是“新增一条笔记”，而是验证：
    # 同一段 ORM 写入代码，在 SQLite 和 PostgreSQL 下是否都能工作。
    note = DatabaseNote(title=payload.title, content=payload.content)
    try:
        db.add(note)
        db.commit()
        db.refresh(note)
        return note
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/notes")
def list_notes(
    db: Session = Depends(get_db),
) -> dict:
    # select(DatabaseNote) 表示查询 database_notes 表对应的 ORM 对象。
    # order_by(DatabaseNote.id.desc()) 让新数据排在前面，方便在 /docs 里观察。
    try:
        statement = select(DatabaseNote).order_by(DatabaseNote.id.desc())
        notes = db.scalars(statement).all()
        return {
            "database_kind": get_database_kind(),
            "database_url": get_safe_database_url(),
            "items": [
                DatabaseNoteRead.model_validate(note)
                for note in notes
            ],
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

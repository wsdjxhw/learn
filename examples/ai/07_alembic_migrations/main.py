from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import (
    EXPECTED_ALEMBIC_HEAD,
    build_database_error_hint,
    check_connection,
    get_alembic_version,
    get_database_kind,
    get_db,
    get_safe_database_url,
    list_table_details,
)
from models import KnowledgeArticle
from schemas import ArticleCreate, ArticleRead, ArticleStatusUpdate

app = FastAPI(title="Alembic Migration Practice")


@app.get("/health")
def health() -> dict:
    # 普通健康检查只说明 FastAPI 进程能响应。
    # 这个模块不会在启动时 create_all，因为本节目标就是学习 Alembic 管结构。
    return {
        "status": "ok",
        "database_kind": get_database_kind(),
        "database_url": get_safe_database_url(),
    }


@app.get("/db/health")
def database_health() -> dict:
    # 数据库健康检查：确认数据库连接能不能建立。
    return check_connection()


@app.get("/migration/status")
def migration_status() -> dict:
    # Alembic 当前版本来自数据库里的 alembic_version 表。
    # current_version 为 None 通常表示你还没有执行过 alembic upgrade。
    try:
        current_version = get_alembic_version()
        return {
            "database_kind": get_database_kind(),
            "database_url": get_safe_database_url(),
            "current_version": current_version,
            "expected_head": EXPECTED_ALEMBIC_HEAD,
            "is_latest": current_version == EXPECTED_ALEMBIC_HEAD,
            "hint": "如果 is_latest 是 false，执行 python -m alembic upgrade head。",
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/db/tables")
def database_tables() -> dict:
    # 查看真实数据库结构。
    # 练习 upgrade / downgrade 时，这个接口比“猜测迁移是否成功”更可靠。
    try:
        return {
            "database_kind": get_database_kind(),
            "database_url": get_safe_database_url(),
            "items": list_table_details(),
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/articles", response_model=ArticleRead)
def create_article(
    payload: ArticleCreate,
    db: Session = Depends(get_db),
) -> KnowledgeArticle:
    # payload 来自请求体 JSON，由 Pydantic DTO 校验。
    # db 来自 Depends(get_db)，类比 FastAPI 自动注入数据库会话。
    #
    # 如果你没有执行迁移，这里会因为表不存在而失败。
    # 这正是本模块要观察的真实工程问题：代码启动了，不代表数据库结构已准备好。
    article = KnowledgeArticle(
        title=payload.title,
        content=payload.content,
        status=payload.status,
    )
    try:
        db.add(article)
        db.commit()
        db.refresh(article)
        return article
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "hint": build_database_error_hint(exc),
            },
        ) from exc


@app.get("/articles")
def list_articles(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    # status 是查询参数，来自 URL，例如 /articles?status=published。
    # 它用于观察第二个迁移新增的 status 字段是否真的能查询。
    try:
        statement = select(KnowledgeArticle).order_by(KnowledgeArticle.id.desc())
        if status:
            statement = statement.where(KnowledgeArticle.status == status)
        articles = db.scalars(statement).all()
        return {
            "items": [ArticleRead.model_validate(article) for article in articles],
        }
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "hint": build_database_error_hint(exc),
            },
        ) from exc


@app.patch("/articles/{article_id}/status", response_model=ArticleRead)
def update_article_status(
    article_id: int,
    payload: ArticleStatusUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeArticle:
    # article_id 是路径参数，来自 URL 里的 {article_id}。
    # payload 是请求体，只允许传 status。
    try:
        article = db.get(KnowledgeArticle, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        article.status = payload.status
        db.commit()
        db.refresh(article)
        return article
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "hint": build_database_error_hint(exc),
            },
        ) from exc

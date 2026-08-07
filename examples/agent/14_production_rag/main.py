"""
main.py - FastAPI 接口层

职责：把前面各个分层（数据库、模型、权限、解析、检索、rerank、编排、工具、模型服务）
     组装成可被 HTTP 调用的接口。这是整个模块的“入口文件”，
     也是学习者应该第一个打开的文件。

本模块接口一览（按学习顺序）：
- GET  /health              服务健康检查
- POST /demo/seed-docs      一键导入示例文档（不用手动构造文件上传，快速跑通）
- POST /documents/upload    上传真实文件（txt/md/pdf），解析入库
- GET  /documents           当前用户可见的文档列表（体验权限隔离）
- GET  /documents/{id}      文档详情 + 全部片段
- DELETE /documents/{id}    删除文档（只有 owner 或 admin 能删）
- POST  /documents/{id}/share  把文档共享给指定用户（只有 owner/admin 能分享）
- POST /search              手动检索：对比“粗排候选”和“rerank 后结果”
- GET  /tools               查看工具 schema
- POST /tool/run            手动执行 search_documents 工具
- POST /agent/chat          Agent 对话：自动决定是否检索，返回带 sources 的回答
- POST /eval/run            跑评测数据集，输出 recall@n

为什么接口都要注入 user？
每个接口都带当前用户身份（X-API-Key 请求头），用于文档级权限过滤。
这是本模块和前面模块最不一样的地方：不是“问一个接口”，而是“以某人的身份操作”。
"""
import os

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from chunker import split_text
from database import Base, engine, get_db
from document_processor import DocumentParseError, extract_text
from eval_runner import run_eval
from models import Chunk, Document
from permissions import User, can_delete_document, can_view_document, get_current_user
from provider import run_agent_chat
from rag import run_rag_search
from retriever import _visible_documents
from settings import settings
from tool_registry import get_tools
from tools import execute_search_documents

# 示例文档目录：seed-docs 接口从这里读文件
SAMPLE_DOCS_DIR = os.path.join(os.path.dirname(__file__), "sample_docs")
# 上传大小上限：2MB。真实项目里这是必须的，否则一个 5GB 文件能把服务打爆。
MAX_UPLOAD_SIZE = 2 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用启动钩子：自动创建所有表。

    教学版用 create_all 建表（SQLite 方便）。
    为什么真实项目不能直接 create_all？因为它不会“改”已有表，
    生产环境的表结构变更要靠迁移工具（模块 07 的 Alembic）。
    这里是为了快速跑通教学，刻意保留的教学简化。
    """
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="14 生产级 RAG 工程",
    description="文件上传解析、metadata 过滤、文档级权限隔离、rerank、评测前置",
    lifespan=lifespan,
)


# ------------------------- 1. 健康检查 -------------------------

@app.get("/health")
def health():
    """最简单的接口：确认服务活着，顺便显示当前模型模式。"""
    return {
        "status": "ok",
        "module": "14_production_rag",
        "model_mode": settings.model_mode,
    }


# ------------------------- 2. 一键导入示例文档 -------------------------

@app.post("/demo/seed-docs")
def seed_docs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """把 sample_docs 目录下的示例文档导入知识库。

    为什么要有这个接口？
    初学者手动构造 multipart 文件上传容易卡住（表单字段名、文件类型等）。
    这个接口模拟“有人替你把文档传好了”，让你先专注看检索和权限效果。

    每篇示例文档都配好了 metadata 和可见范围：
    - 报销流程 / 请假制度 / 规章制度大全：public（所有人可见）
    - 产品路线图：private，归“上传者”所有（默认 alice），用来演示权限隔离

    幂等设计：同名文档已存在则跳过，重复调用不会产生重复数据。
    """
    specs = [
        {"file": "公司报销流程.txt", "title": "公司报销流程",
         "category": "财务", "tags": "报销,流程,差旅", "visibility": "public"},
        {"file": "员工请假制度.md", "title": "员工请假制度",
         "category": "人事", "tags": "请假,考勤", "visibility": "public"},
        {"file": "公司规章制度大全.txt", "title": "公司规章制度大全",
         "category": "综合", "tags": "制度,规范,报销", "visibility": "public"},
        {"file": "产品路线图-内部机密.md", "title": "产品路线图（内部机密）",
         "category": "产品", "tags": "产品,路线图,机密", "visibility": "private"},
    ]

    created, skipped = [], []
    for spec in specs:
        # 幂等：同名文件已经入库就跳过
        existing = db.scalars(
            select(Document).where(Document.filename == spec["file"])
        ).first()
        if existing:
            skipped.append(spec["file"])
            continue

        file_path = os.path.join(SAMPLE_DOCS_DIR, spec["file"])
        with open(file_path, "rb") as f:
            content = f.read()
        # 和上传接口走完全相同的处理链路：解析 -> 切分 -> 入库
        text, content_type = extract_text(spec["file"], content)
        chunks = split_text(text)

        doc = Document(
            title=spec["title"],
            filename=spec["file"],
            content_type=content_type,
            file_size=len(content),
            content_preview=text[:200],
            owner_id=user.user_id,          # 归属当前上传者
            visibility=spec["visibility"],
            category=spec["category"],
            tags=spec["tags"],
            chunk_count=len(chunks),
        )
        db.add(doc)
        db.flush()  # flush 让 doc.id 先生成，后面建 chunk 需要它
        for i, c in enumerate(chunks):
            db.add(Chunk(document_id=doc.id, index=i, content=c, char_count=len(c)))
        db.commit()
        created.append({
            "title": spec["title"], "chunk_count": len(chunks), "visibility": spec["visibility"],
        })

    return {"created": created, "skipped": skipped}


# ------------------------- 3. 文档上传（文件解析 + 切分 + 入库） -------------------------

@app.post("/documents/upload", response_model=schemas.DocumentUploadResult)
def upload_document(
    # UploadFile = File(...)：FastAPI 从 multipart/form-data 里取文件字段。
    # 参数来源：前端用 FormData 上传时，字段名叫 file。
    file: UploadFile = File(..., description="要上传的文档文件（txt/md/pdf）"),
    # Form(...)：同一请求里的普通文本字段（文档的 metadata）。
    # 混用 File 和 Form 是文件上传接口的标准写法。
    title: str = Form(None, description="文档标题，不传则用文件名"),
    category: str = Form(None, description="文档分类，例如 财务/人事/产品"),
    tags: str = Form(None, description="标签，逗号分隔，例如 '报销,流程'"),
    visibility: str = Form("private", description="可见范围：public 或 private"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """真实文件上传入口。本模块的“核心新能力”之一。

    处理链路（和 seed-docs 完全一致，这里是真的网络文件）：
        读字节 -> 限制大小 -> 解析成文本 -> 切分 -> 写 documents + chunks -> 返回
    """
    # visibility 白名单校验：用户可能传错，后端必须兜底。
    if visibility not in ("public", "private"):
        raise HTTPException(status_code=400, detail="visibility 只能是 public 或 private")

    # 读文件字节。file.file 是 FastAPI 底层临时文件对象，read() 是同步读。
    content = file.file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        # 真实项目限制上传大小：413 = Payload Too Large
        raise HTTPException(
            status_code=413,
            detail=f"文件超过 {MAX_UPLOAD_SIZE // 1024 // 1024}MB 上限",
        )

    # 解析：按扩展名选解析器。解析失败会被捕获并转成友好的 400 错误。
    try:
        text, content_type = extract_text(file.filename or "", content)
    except DocumentParseError as e:
        # 把业务异常转成 HTTP 400，而不是让 Python 栈直接暴露给前端
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 解析出来的文本为空（例如文件全是空白字符）：真实项目必须拦截
    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空，无法入库")

    chunks = split_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="没有可切分的文本内容")

    # 标题默认用文件名（去掉扩展名），更贴近用户习惯
    final_title = title or os.path.splitext(file.filename or "未命名")[0]

    # 写 documents 行 + 多个 chunks 行。
    # 一个事务（add + commit）保证要么全成功要么全失败，
    # 不会出现“文档记录建好了 chunk 没写入”的脏数据。
    doc = Document(
        title=final_title,
        filename=file.filename or "",
        content_type=content_type,
        file_size=len(content),
        content_preview=text[:200],
        owner_id=user.user_id,
        visibility=visibility,
        category=category,
        tags=tags,
        chunk_count=len(chunks),
    )
    db.add(doc)
    db.flush()
    for i, c in enumerate(chunks):
        db.add(Chunk(document_id=doc.id, index=i, content=c, char_count=len(c)))
    db.commit()
    db.refresh(doc)  # refresh 把数据库生成的时间等字段同步回对象

    return schemas.DocumentUploadResult(
        document_id=doc.id, title=doc.title, filename=doc.filename,
        content_type=doc.content_type, file_size=doc.file_size,
        chunk_count=doc.chunk_count, owner_id=doc.owner_id,
        visibility=doc.visibility, category=doc.category, tags=doc.tags,
    )


# ------------------------- 4. 文档列表与详情（体验权限隔离） -------------------------

@app.get("/documents", response_model=list[schemas.DocumentListItem])
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户可见的文档列表。

    教学观察点：用不同 API Key 调用，看到的文档数量不同。
    alice 能看到自己的私有文档，bob 看不到（只看到 public 的 3 篇）。
    """
    visible = _visible_documents(db, user)
    # 按 id 排序，保证返回顺序稳定
    visible.sort(key=lambda d: d.id)
    return [
        schemas.DocumentListItem(
            id=d.id, title=d.title, filename=d.filename,
            content_type=d.content_type, file_size=d.file_size,
            owner_id=d.owner_id, visibility=d.visibility,
            category=d.category, tags=d.tags,
            chunk_count=d.chunk_count,
            created_at=str(d.created_at),
        )
        for d in visible
    ]


@app.get("/documents/{doc_id}", response_model=schemas.DocumentDetail)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """文档详情：文档信息 + 原文预览 + 全部片段。"""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not can_view_document(user, doc):
        # 数据级权限：没有权限直接拒绝，而不是返回空内容
        raise HTTPException(status_code=403, detail="你无权查看该文档")

    chunks = sorted(doc.chunks, key=lambda c: c.index)
    return schemas.DocumentDetail(
        id=doc.id, title=doc.title, filename=doc.filename,
        content_type=doc.content_type, file_size=doc.file_size,
        owner_id=doc.owner_id, visibility=doc.visibility,
        category=doc.category, tags=doc.tags,
        chunk_count=doc.chunk_count, created_at=str(doc.created_at),
        content_preview=doc.content_preview,
        chunks=[schemas.ChunkItem(index=c.index, content=c.content, char_count=c.char_count) for c in chunks],
    )


@app.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除文档。只有 owner 或 admin 能删（写操作权限更严）。"""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not can_delete_document(user, doc):
        raise HTTPException(status_code=403, detail="只有文档所有者或管理员可以删除")
    # delete 会触发 models.py 里声明的级联删除：chunks 一起删
    db.delete(doc)
    db.commit()
    return {"deleted": True, "document_id": doc_id}


# ------------------------- 4.5 文档共享（练习一：分享可见） -------------------------

@app.post("/documents/{doc_id}/share", response_model=schemas.ShareResult)
def share_document(
    doc_id: int,
    req: schemas.ShareRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """把文档共享给指定用户。

    这是练习一要求的“改接口”部分：存储字段（models.py）和权限判断（permissions.py）
    都改好之后，必须有一个接口能写 shared_with，否则没法通过 HTTP 验证共享效果。

    为什么复用 can_delete_document 而不是新写一个“能分享”的判断？
    分享是一种写操作（改变文档的可见范围），写操作权限从严：
    只有 owner 自己或 admin 能分享。别人能看你的文档，不等于能分享你的文档。
    """
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not can_delete_document(user, doc):
        raise HTTPException(status_code=403, detail="只有文档所有者或管理员可以分享")

    # 归一化：去掉空格、过滤空串，保证和 permissions.py 里的 split 规则一致。
    # 真实项目里分享通常落在单独一张关联表（document_shares），教学版直接更新字段。
    shared = ",".join(u.strip() for u in req.user_ids if u.strip())
    # 空列表 = 取消所有共享（shared_with 存 None，permissions.py 按“未共享”处理）
    doc.shared_with = shared or None
    db.commit()
    db.refresh(doc)
    return schemas.ShareResult(
        document_id=doc.id,
        shared_with=doc.shared_with or "",
    )


# ------------------------- 5. 手动检索（对比粗排和精排） -------------------------

@app.post("/search", response_model=schemas.SearchResponse)
def search(
    req: schemas.SearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手动检索接口。本模块的“教学核心接口”。

    返回里同时给了 raw_candidates（粗排）和 reranked_results（精排），
    这是有意设计的：让你直接对比“检索顺序”和“rerank 后顺序”有什么不同，
    以及 metadata 过滤、权限过滤如何改变结果。
    """
    result = run_rag_search(
        db, user,
        query=req.query,
        category=req.category,
        tags=req.tags,
        top_k=req.top_k,
        top_n=req.top_n,
    )

    # 粗排候选转 DTO
    raw = [
        schemas.SearchChunkResult(
            chunk_id=c.chunk.id, document_id=c.document.id,
            document_title=c.document.title, chunk_index=c.chunk.index,
            content=c.chunk.content, score=float(c.score),
        )
        for c in result.candidates
    ]
    # 精排结果转 DTO
    reranked = [
        schemas.SearchChunkResult(
            chunk_id=r.candidate.chunk.id, document_id=r.candidate.document.id,
            document_title=r.candidate.document.title,
            chunk_index=r.candidate.chunk.index,
            content=r.candidate.chunk.content, score=round(r.score, 3),
        )
        for r in result.reranked
    ]

    return schemas.SearchResponse(
        query=req.query,
        user_id=user.user_id,
        raw_candidates=raw,
        reranked_results=reranked,
        filtered_documents=result.filtered_documents,
    )


# ------------------------- 6. 工具相关接口 -------------------------

@app.get("/tools")
def list_tools():
    """查看工具 schema（模型能调用哪些工具、参数长什么样）。"""
    return {"tools": get_tools()}


@app.post("/tool/run", response_model=schemas.AgentChatResponse)
def run_tool(
    req: schemas.ToolRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手动执行工具。方便你不经过模型，直接观察工具行为。

    返回结构故意复用 AgentChatResponse：
    used_tool 固定 true，sources 是检索结果，answer 是执行说明。
    这样前端可以统一渲染“工具调用结果”。
    """
    if req.tool_name != "search_documents":
        raise HTTPException(status_code=400, detail="本模块只有 search_documents 一个工具")

    result = execute_search_documents(db, user, req.arguments)
    return schemas.AgentChatResponse(
        used_tool=True,
        tool_name="search_documents",
        answer=result.get("note", ""),
        sources=[schemas.AgentSource(**s) for s in result.get("sources", [])],
    )


# ------------------------- 7. Agent 对话 -------------------------

@app.post("/agent/chat", response_model=schemas.AgentChatResponse)
def agent_chat(
    req: schemas.AgentChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Agent 对话：自动决定“要不要检索”，返回带 sources 的回答。

    这是模块 13 已经有的模式，本模块的差异是：
    检索结果经过了权限过滤、metadata 过滤和 rerank。
    """
    result = run_agent_chat(db, user, req.message)
    return schemas.AgentChatResponse(
        used_tool=result["used_tool"],
        tool_name="search_documents" if result["used_tool"] else None,
        answer=result["answer"],
        sources=[schemas.AgentSource(**s) for s in result["sources"]],
    )


# ------------------------- 8. 评测前置 -------------------------

@app.post("/eval/run", response_model=schemas.EvalRunResponse)
def eval_run(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """跑一遍评测数据集，输出 recall@n。

    用不同身份跑结果可能不同（私有文档权限）：
    - alice / admin：产品路线图 case 命中，recall 更高；
    - bob：看不到私有文档，对应 case 失败。
    这演示了“评测必须贴近真实权限环境”。
    """
    return run_eval(db, user, top_n=3)

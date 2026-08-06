import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import ToolAuditLog
from permissions import check_tool_permission, get_current_auth, new_request_id, write_tool_audit_log
from provider import decide_next_action, generate_final_answer, get_provider_name
from rag import create_document, list_chunks, list_documents, seed_demo_documents
from schemas import (
    AuditLogResponse,
    AuthContext,
    ChatRequest,
    ChatResponse,
    DocumentCreate,
    ToolInfo,
    ToolRunRequest,
    ToolRunResponse,
)
from settings import get_settings
from tool_registry import get_tool_definition, list_tool_definitions
from tools import run_tool


# main.py 是 Web API 层。
# Java 类比：可以理解成 Controller，只负责接收请求、调用业务层、返回 DTO。
app = FastAPI(title="RAG Tool Agent Teaching Demo")


@app.on_event("startup")
def on_startup() -> None:
    # 服务启动时创建 documents、chunks、tool_audit_logs 表。
    # 教学版用 create_all；生产项目应该使用 Alembic 迁移。
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "module": "13_rag_tool_agent",
        "model_mode": settings.model_mode,
        "provider": get_provider_name(),
        "database_url": settings.database_url,
        "has_deepseek_api_key": bool(settings.deepseek_api_key),
    }


@app.get("/auth/whoami", response_model=AuthContext)
def whoami(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    # 先跑这个接口，能确认当前 X-API-Key 被识别成什么用户和角色。
    # 不传 X-API-Key 时，教学版默认是 viewer。
    return auth


@app.get("/tools", response_model=list[ToolInfo])
def list_tools(auth: AuthContext = Depends(get_current_auth)) -> list[ToolInfo]:
    # /tools 展示工具注册表经过权限判断后的结果。
    # 本模块只有一个 search_documents 工具，重点看它的描述和参数。
    items: list[ToolInfo] = []
    for tool in list_tool_definitions():
        permission = check_tool_permission(auth, tool)
        items.append(
            ToolInfo(
                name=tool.name,
                description=tool.description,
                tool_type=tool.tool_type,
                risk_level=tool.risk_level,
                allowed_roles=list(tool.allowed_roles),
                expose_to_model=tool.expose_to_model,
                enabled=tool.enabled,
                is_allowed_for_current_user=permission.allowed,
                permission_reason=permission.reason,
            )
        )
    return items


@app.post("/documents", status_code=201)
def ingest_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # 知识库录入接口：把一篇文档切成 chunks 并入库。
    # 对应真实项目里的“文档上传/导入”流程（模块 14 会升级成文件上传 + 解析）。
    return create_document(
        db=db,
        title=payload.title,
        content=payload.content,
        chunk_size=payload.chunk_size,
        overlap=payload.overlap,
    )


@app.get("/documents")
def get_documents(db: Session = Depends(get_db)) -> dict[str, Any]:
    # 查看知识库里已经录入了哪些文档。
    return {"items": list_documents(db)}


@app.get("/documents/{document_id}/chunks")
def get_document_chunks(document_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    # 查看一篇文档被切成了哪些片段，学习时用来确认切分结果。
    chunks = list_chunks(db, document_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found or has no chunks")
    return {"items": chunks}


@app.post("/demo/seed")
def seed_demo(db: Session = Depends(get_db)) -> dict[str, Any]:
    # 教学便利接口：一键写入三篇示例文档（报销、请假、行为规范），
    # 让你不用手敲长文本就能立刻测试 RAG Agent。
    created = seed_demo_documents(db)
    return {"message": "示例文档已入库。", "documents": created}


@app.post("/tool/run", response_model=ToolRunResponse)
def run_tool_manually(
    payload: ToolRunRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ToolRunResponse:
    # 这是本模块最重要的接口之一：绕过 Agent 自动决策，手动验证工具执行。
    # 学 RAG 工具时，先手动跑通“检索返回什么”，再让 Agent 自动选工具会更清楚。
    tool = get_tool_definition(payload.tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"未知工具：{payload.tool_name}")

    request_id = new_request_id()
    permission = check_tool_permission(auth, tool, payload.arguments)
    if not permission.allowed:
        write_tool_audit_log(
            db=db,
            request_id=request_id,
            auth=auth,
            tool=tool,
            allowed=False,
            reason=permission.reason,
            arguments=payload.arguments,
            error=permission.reason,
        )
        raise HTTPException(status_code=403, detail=permission.reason)

    tool_output = run_tool(db=db, tool_name=tool.name, arguments=payload.arguments)
    write_tool_audit_log(
        db=db,
        request_id=request_id,
        auth=auth,
        tool=tool,
        allowed=True,
        reason="手动执行检索工具。",
        arguments=payload.arguments,
        result=tool_output,
        error=None if tool_output.get("ok") else str(tool_output.get("error")),
    )

    return ToolRunResponse(
        request_id=request_id,
        auth=auth,
        tool_name=payload.tool_name,
        allowed=True,
        permission_reason=permission.reason,
        tool_output=tool_output,
        # sources 就是检索到的相关片段，是“回答的依据”，前端可以直接展示。
        sources=tool_output.get("results", []),
    )


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(
    payload: ChatRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ChatResponse:
    # 完整 RAG Agent 链路：
    # 1. 根据当前用户权限过滤可见工具；
    # 2. 让 mock / DeepSeek 判断“这个问题需不需要检索”；
    # 3. 需要检索就调用 search_documents，拿到 sources；
    # 4. 不需要检索就直接回答；
    # 5. 最终回答带上 sources，检索不到资料时明确说明不足。
    steps: list[dict[str, Any]] = [{"step": "user_input", "message": payload.message, "auth": auth.model_dump()}]

    visible_tools = []
    for tool in list_tool_definitions():
        if tool.expose_to_model and check_tool_permission(auth, tool).allowed:
            visible_tools.append(tool.to_openai_tool_schema())

    steps.append({"step": "visible_tools", "tool_names": [item["function"]["name"] for item in visible_tools]})

    decision = decide_next_action(
        user_message=payload.message,
        tool_schemas=visible_tools,
        allow_tool=payload.allow_tool,
    )
    steps.append({"step": "model_decision", "decision": decision})

    if decision["type"] == "answer":
        # 模型判断不需要检索，直接回答，不调用工具。
        return ChatResponse(
            reply=decision["answer"],
            auth=auth,
            used_tool=False,
            tool_name=None,
            tool_output=None,
            sources=[],
            steps=steps,
        )

    tool = get_tool_definition(decision["tool_name"])
    if tool is None:
        reply = f"模型请求了未注册工具：{decision['tool_name']}。后端已拒绝执行。"
        steps.append({"step": "permission_denied", "reason": reply})
        return ChatResponse(
            reply=reply,
            auth=auth,
            used_tool=False,
            tool_name=None,
            tool_output=None,
            sources=[],
            steps=steps,
        )

    # 即使工具来自可见列表，后端仍然再次做权限检查（防模型被诱导生成未授权工具名）。
    request_id = new_request_id()
    permission = check_tool_permission(auth, tool, decision["arguments"])
    if not permission.allowed:
        write_tool_audit_log(
            db=db,
            request_id=request_id,
            auth=auth,
            tool=tool,
            allowed=False,
            reason=permission.reason,
            arguments=decision["arguments"],
            error=permission.reason,
        )
        steps.append({"step": "permission_denied", "request_id": request_id, "reason": permission.reason})
        return ChatResponse(
            reply=f"工具调用被权限系统拦截：{permission.reason}",
            auth=auth,
            used_tool=False,
            tool_name=tool.name,
            tool_output=None,
            sources=[],
            steps=steps,
        )

    tool_output = run_tool(db=db, tool_name=tool.name, arguments=decision["arguments"])
    write_tool_audit_log(
        db=db,
        request_id=request_id,
        auth=auth,
        tool=tool,
        allowed=True,
        reason=permission.reason,
        arguments=decision["arguments"],
        result=tool_output,
        error=None if tool_output.get("ok") else str(tool_output.get("error")),
    )
    steps.append({"step": "tool_execution", "request_id": request_id, "tool_output": tool_output})

    # sources 进入最终回答：既出现在 reply 文本里，也作为独立字段返回给前端。
    sources = tool_output.get("results", [])
    reply = generate_final_answer(payload.message, tool_output)
    steps.append({"step": "final_answer", "reply": reply, "source_count": len(sources)})

    return ChatResponse(
        reply=reply,
        auth=auth,
        used_tool=True,
        tool_name=tool.name,
        tool_output=tool_output,
        sources=sources,
        steps=steps,
    )


@app.get("/audit/logs", response_model=list[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[AuditLogResponse]:
    # 审计日志接口让学习者验证：成功检索、越权尝试都会留下记录。
    # 教学版允许普通用户查看自己的日志；管理员可以查看所有日志。
    stmt = select(ToolAuditLog).order_by(ToolAuditLog.id.desc()).limit(limit)
    if auth.role != "admin":
        stmt = (
            select(ToolAuditLog)
            .where(ToolAuditLog.user_id == auth.user_id)
            .order_by(ToolAuditLog.id.desc())
            .limit(limit)
        )

    rows = db.execute(stmt).scalars().all()
    return [
        AuditLogResponse(
            id=row.id,
            request_id=row.request_id,
            user_id=row.user_id,
            api_key_name=row.api_key_name,
            role=row.role,
            tool_name=row.tool_name,
            tool_type=row.tool_type,
            risk_level=row.risk_level,
            allowed=row.allowed,
            reason=row.reason,
            arguments=json.loads(row.arguments_json),
            result=json.loads(row.result_json),
            error=row.error,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]

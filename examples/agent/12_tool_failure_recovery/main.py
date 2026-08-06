import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db, init_db
from confirmations import (
    approve_confirmation,
    create_pending_confirmation,
    get_confirmation_for_user,
    list_confirmations,
    reject_confirmation,
    should_require_confirmation,
    to_confirmation_response,
)
from models import ToolAuditLog
from permissions import check_tool_permission, get_current_auth, new_request_id, write_tool_audit_log
from provider import decide_next_action, generate_final_answer, get_provider_name
from recovery import execute_tool_with_recovery
from schemas import (
    AuditLogResponse,
    AuthContext,
    ChatRequest,
    ChatResponse,
    ConfirmationApproveRequest,
    ConfirmationRejectRequest,
    ConfirmationResponse,
    RecoveryPreviewRequest,
    RecoveryPreviewResponse,
    ToolInfo,
    ToolRunRequest,
    ToolRunResponse,
)
from settings import get_settings
from tool_registry import get_tool_definition, list_tool_definitions


# main.py 是 Web API 层。
# Java 类比：可以理解成 Controller，只负责接收请求、调用业务层、返回 DTO。
app = FastAPI(title="Agent Tool Failure Recovery Teaching Demo")


@app.on_event("startup")
def on_startup() -> None:
    # 服务启动时创建审计日志表。
    # 教学版用 create_all；生产项目应该使用 Alembic 迁移。
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "module": "12_tool_failure_recovery",
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
def list_tools(
    include_forbidden: bool = Query(default=False, description="是否返回当前用户无权调用的工具。"),
    auth: AuthContext = Depends(get_current_auth),
) -> list[ToolInfo]:
    # /tools 展示工具注册表经过权限判断后的结果。
    # include_forbidden=false 时更接近真实项目：只把当前用户能调用的工具暴露给模型。
    items: list[ToolInfo] = []
    for tool in list_tool_definitions():
        permission = check_tool_permission(auth, tool)
        if not include_forbidden and not permission.allowed:
            continue
        items.append(
            ToolInfo(
                name=tool.name,
                description=tool.description,
                tool_type=tool.tool_type,
                risk_level=tool.risk_level,
                allowed_roles=list(tool.allowed_roles),
                requires_confirmation=should_require_confirmation(tool),
                timeout_seconds=tool.timeout_seconds,
                max_retries=tool.max_retries,
                fallback_tool_name=tool.fallback_tool_name,
                expose_to_model=tool.expose_to_model,
                enabled=tool.enabled,
                is_allowed_for_current_user=permission.allowed,
                permission_reason=permission.reason,
            )
        )
    return items


@app.post("/tool/run", response_model=ToolRunResponse)
def run_tool_manually(
    payload: ToolRunRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ToolRunResponse:
    # 这是本模块最重要的接口之一：绕过模型，手动验证权限和工具执行。
    # 学工具权限时，先手动跑通比一开始看模型自动选择更清楚。
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

    if should_require_confirmation(tool, payload.arguments):
        # 有权限不等于可以立刻执行。
        # 高风险写工具先创建确认单，等待 /confirmations/{id}/approve。
        confirmation = create_pending_confirmation(
            db=db,
            request_id=request_id,
            auth=auth,
            tool=tool,
            arguments=payload.arguments,
            confirm_reason="工具风险等级较高，需要人工确认后执行。",
        )
        tool_output = {
            "ok": True,
            "tool_name": tool.name,
            "requires_confirmation": True,
            "confirmation_id": confirmation.confirmation_id,
            "status": confirmation.status,
        }
        write_tool_audit_log(
            db=db,
            request_id=request_id,
            auth=auth,
            tool=tool,
            allowed=True,
            reason="权限检查通过，但工具需要人工确认，已创建待确认单。",
            arguments=payload.arguments,
            result=tool_output,
        )
        return ToolRunResponse(
            request_id=request_id,
            auth=auth,
            tool_name=payload.tool_name,
            allowed=True,
            permission_reason=permission.reason,
            tool_output=tool_output,
            requires_confirmation=True,
            confirmation=to_confirmation_response(confirmation),
        )

    tool_output = execute_tool_with_recovery(db=db, auth=auth, tool=tool, arguments=payload.arguments)
    write_tool_audit_log(
        db=db,
        request_id=request_id,
        auth=auth,
        tool=tool,
        allowed=True,
        reason=permission.reason,
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
        requires_confirmation=False,
        confirmation=None,
    )


@app.post("/tool/recovery-preview", response_model=RecoveryPreviewResponse)
def preview_tool_recovery(
    payload: RecoveryPreviewRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> RecoveryPreviewResponse:
    # 这个接口专门用来学习失败恢复策略。
    # 它绕过 Agent 自动决策，但仍然保留权限检查、重试、降级和审计日志。
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

    tool_output = execute_tool_with_recovery(db=db, auth=auth, tool=tool, arguments=payload.arguments)
    write_tool_audit_log(
        db=db,
        request_id=request_id,
        auth=auth,
        tool=tool,
        allowed=True,
        reason="执行工具失败恢复预览。",
        arguments=payload.arguments,
        result=tool_output,
        error=None if tool_output.get("ok") else str(tool_output.get("error")),
    )
    return RecoveryPreviewResponse(
        request_id=request_id,
        auth=auth,
        tool_name=tool.name,
        recovery_action=tool_output.get("recovery_action", "none"),
        tool_output=tool_output,
        attempts=tool_output.get("attempts", []),
    )


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(
    payload: ChatRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ChatResponse:
    # 完整 Agent 链路：
    # 1. 根据当前用户权限过滤可见工具；
    # 2. 让 mock / DeepSeek 在可见工具中做选择；
    # 3. 即使工具来自可见列表，后端仍然再次做权限检查；
    # 4. 执行工具并写审计日志；
    # 5. 把工具结果整理成最终回答。
    steps: list[dict[str, Any]] = [{"step": "user_input", "message": payload.message, "auth": auth.model_dump()}]

    visible_tools = []
    for tool in list_tool_definitions():
        if tool.expose_to_model and check_tool_permission(auth, tool).allowed:
            visible_tools.append(tool.to_openai_tool_schema())

    steps.append({"step": "visible_tools", "tool_names": [item["function"]["name"] for item in visible_tools]})

    decision = decide_next_action(
        user_message=payload.message,
        tool_schemas=visible_tools,
        auth_user_id=auth.user_id,
        allow_tool=payload.allow_tool,
    )
    steps.append({"step": "model_decision", "decision": decision})

    if decision["type"] == "answer":
        return ChatResponse(
            reply=decision["answer"],
            auth=auth,
            used_tool=False,
            tool_name=None,
            tool_output=None,
            requires_confirmation=False,
            confirmation=None,
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
            requires_confirmation=False,
            confirmation=None,
            steps=steps,
        )

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
            requires_confirmation=False,
            confirmation=None,
            steps=steps,
        )

    if should_require_confirmation(tool, decision["arguments"]):
        confirmation = create_pending_confirmation(
            db=db,
            request_id=request_id,
            auth=auth,
            tool=tool,
            arguments=decision["arguments"],
            confirm_reason="Agent 选择了高风险写工具，需要人工确认后执行。",
        )
        tool_output = {
            "ok": True,
            "tool_name": tool.name,
            "requires_confirmation": True,
            "confirmation_id": confirmation.confirmation_id,
            "status": confirmation.status,
        }
        write_tool_audit_log(
            db=db,
            request_id=request_id,
            auth=auth,
            tool=tool,
            allowed=True,
            reason="Agent 工具权限通过，但因高风险写操作进入人工确认。",
            arguments=decision["arguments"],
            result=tool_output,
        )
        steps.append({"step": "confirmation_required", "request_id": request_id, "tool_output": tool_output})
        confirmation_dto = to_confirmation_response(confirmation)
        return ChatResponse(
            reply=f"这个操作需要人工确认后才能执行，确认单 ID：{confirmation.confirmation_id}",
            auth=auth,
            used_tool=False,
            tool_name=tool.name,
            tool_output=tool_output,
            requires_confirmation=True,
            confirmation=confirmation_dto,
            steps=steps,
        )

    tool_output = execute_tool_with_recovery(db=db, auth=auth, tool=tool, arguments=decision["arguments"])
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

    reply = generate_final_answer(payload.message, tool_output)
    steps.append({"step": "final_answer", "reply": reply})

    return ChatResponse(
        reply=reply,
        auth=auth,
        used_tool=True,
        tool_name=tool.name,
        tool_output=tool_output,
        requires_confirmation=False,
        confirmation=None,
        steps=steps,
    )


@app.get("/confirmations", response_model=list[ConfirmationResponse])
def get_confirmations(
    status: str | None = Query(default=None, description="可选：只查看 pending/executed/rejected/failed。"),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[ConfirmationResponse]:
    # 确认单列表模拟真实后台工作台。
    # admin 能看到所有确认单，普通用户只能看到自己发起的确认单。
    confirmations = list_confirmations(db, auth, status, limit)
    return [to_confirmation_response(item) for item in confirmations]


@app.get("/confirmations/{confirmation_id}", response_model=ConfirmationResponse)
def get_confirmation(
    confirmation_id: str,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ConfirmationResponse:
    confirmation = get_confirmation_for_user(db, confirmation_id, auth)
    return to_confirmation_response(confirmation)


@app.post("/confirmations/{confirmation_id}/approve", response_model=ConfirmationResponse)
def approve_pending_confirmation(
    confirmation_id: str,
    payload: ConfirmationApproveRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ConfirmationResponse:
    # 批准后才真正执行危险工具。
    # 这是本节最核心的接口，读代码时应该从这里追到 confirmations.py。
    confirmation = approve_confirmation(db, confirmation_id, auth, payload.reason)
    return to_confirmation_response(confirmation)


@app.post("/confirmations/{confirmation_id}/reject", response_model=ConfirmationResponse)
def reject_pending_confirmation(
    confirmation_id: str,
    payload: ConfirmationRejectRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ConfirmationResponse:
    # 拒绝后不会执行工具，只保存拒绝原因。
    confirmation = reject_confirmation(db, confirmation_id, auth, payload.reason)
    return to_confirmation_response(confirmation)


@app.get("/audit/logs", response_model=list[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[AuditLogResponse]:
    # 审计日志接口让学习者验证：成功、失败、越权都会留下记录。
    # 教学版允许普通用户查看自己的日志；管理员可以查看所有日志。
    stmt = select(ToolAuditLog).order_by(ToolAuditLog.id.desc()).limit(limit)
    if auth.role != "admin":
        stmt = select(ToolAuditLog).where(ToolAuditLog.user_id == auth.user_id).order_by(ToolAuditLog.id.desc()).limit(limit)

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

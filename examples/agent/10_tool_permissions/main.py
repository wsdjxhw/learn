import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import ToolAuditLog
from permissions import check_tool_permission, get_current_auth, new_request_id, write_tool_audit_log
from provider import decide_next_action, generate_final_answer, get_provider_name
from schemas import AuditLogResponse, AuthContext, ChatRequest, ChatResponse, ToolInfo, ToolRunRequest, ToolRunResponse
from settings import get_settings
from tool_registry import get_tool_definition, list_tool_definitions
from tools import run_tool


# main.py 是 Web API 层。
# Java 类比：可以理解成 Controller，只负责接收请求、调用业务层、返回 DTO。
app = FastAPI(title="Agent Tool Permissions Teaching Demo")


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
        "module": "10_tool_permissions",
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

    tool_output = run_tool(payload.tool_name, payload.arguments, db=db)
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
        if check_tool_permission(auth, tool).allowed:
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
            steps=steps,
        )

    tool = get_tool_definition(decision["tool_name"])
    if tool is None:
        reply = f"模型请求了未注册工具：{decision['tool_name']}。后端已拒绝执行。"
        steps.append({"step": "permission_denied", "reason": reply})
        return ChatResponse(reply=reply, auth=auth, used_tool=False, tool_name=None, tool_output=None, steps=steps)

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
            steps=steps,
        )

    tool_output = run_tool(tool.name, decision["arguments"], db=db)
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
        steps=steps,
    )


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

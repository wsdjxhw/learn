import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PendingConfirmation
from permissions import write_tool_audit_log
from schemas import AuthContext, ConfirmationResponse
from tool_registry import ToolDefinition, get_tool_definition
from tools import run_tool


def should_require_confirmation(tool: ToolDefinition, arguments: dict[str, Any] | None = None) -> bool:
    # 本节把“风险等级”真正接入执行策略。
    # 上一节 risk_level 主要用于展示和审计；这一节新增规则：
    # 高风险写工具不能直接执行，必须先创建待确认单。
    #
    # 为什么不简单写 tool.risk_level == "high"？
    # 因为 list_audit_logs 也是 high，但它是 admin 读工具，不需要确认。
    #
    # 练习三：create_support_ticket 是“参数级风险”。
    # 同一个工具，普通优先级直接执行，high 优先级才需要人工确认。
    # 关键：判断必须看“这次调用传的参数”，不能看工具注册表里的参数声明。
    arguments = arguments or {}
    if tool.name == "create_support_ticket":
        return str(arguments.get("priority", "")).lower() == "high"

    return tool.requires_confirmation or (tool.tool_type == "write" and tool.risk_level == "high")


def new_confirmation_id() -> str:
    # confirmation_id 是给前端和调用方使用的确认单 ID。
    # 不直接暴露数据库自增 id，能减少接口和数据库实现的耦合。
    return "CONF-" + uuid.uuid4().hex[:12]


def create_pending_confirmation(
    db: Session,
    request_id: str,
    auth: AuthContext,
    tool: ToolDefinition,
    arguments: dict[str, Any],
    confirm_reason: str,
) -> PendingConfirmation:
    # 创建待确认单时，不执行真实工具。
    # 这一步只是把“准备做什么”持久化下来，等待后续 approve / reject。
    confirmation = PendingConfirmation(
        confirmation_id=new_confirmation_id(),
        request_id=request_id,
        requester_user_id=auth.user_id,
        requester_api_key_name=auth.api_key_name,
        requester_role=auth.role,
        tool_name=tool.name,
        tool_type=tool.tool_type,
        risk_level=tool.risk_level,
        arguments_json=json.dumps(arguments, ensure_ascii=False),
        status="pending",
        confirm_reason=confirm_reason,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(confirmation)
    db.commit()
    db.refresh(confirmation)
    return confirmation


def get_confirmation_for_user(
    db: Session,
    confirmation_id: str,
    auth: AuthContext,
) -> PendingConfirmation:
    # 普通用户只能查看自己发起的确认单；admin 可以查看所有确认单。
    stmt = select(PendingConfirmation).where(PendingConfirmation.confirmation_id == confirmation_id)
    if auth.role != "admin":
        stmt = stmt.where(PendingConfirmation.requester_user_id == auth.user_id)

    confirmation = db.execute(stmt).scalar_one_or_none()
    if confirmation is None:
        raise HTTPException(status_code=404, detail="确认单不存在，或你无权查看这张确认单。")
    return confirmation


def list_confirmations(
    db: Session,
    auth: AuthContext,
    status: str | None,
    limit: int,
) -> list[PendingConfirmation]:
    # 列表接口用于模拟后台工作台。
    # 真实项目里，管理员会在工作台查看 pending 危险操作并决定批准或拒绝。
    stmt = select(PendingConfirmation).order_by(PendingConfirmation.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(PendingConfirmation.status == status)
    if auth.role != "admin":
        stmt = stmt.where(PendingConfirmation.requester_user_id == auth.user_id)
    return list(db.execute(stmt).scalars().all())


def approve_confirmation(
    db: Session,
    confirmation_id: str,
    approver: AuthContext,
    reason: str,
) -> PendingConfirmation:
    # approve 是本模块核心：批准后才真正调用工具。
    # 教学版只允许 admin 批准。真实项目可能要求“发起人和批准人不能是同一个人”。
    if approver.role != "admin":
        raise HTTPException(status_code=403, detail="只有 admin 可以批准危险操作。")
    
    confirmation = get_confirmation_for_user(db, confirmation_id, approver)
    if confirmation.status != "pending":
        if confirmation.status == "executed":
            raise HTTPException(status_code=409, detail="确认单已批准并执行成功，不能重复批准。")
        raise HTTPException(status_code=409, detail=f"确认单当前状态是 {confirmation.status}，不能重复批准。")
    
    if confirmation.expires_at and confirmation.expires_at < datetime.utcnow():
        raise HTTPException(status_code=409, detail="确认单已过期，不能批准。")

    if approver.user_id == confirmation.requester_user_id:
        raise HTTPException(status_code=403, detail="不能批准自己发起的确认单。")

    tool = get_tool_definition(confirmation.tool_name)
    if tool is None:
        raise HTTPException(status_code=400, detail=f"确认单里的工具 {confirmation.tool_name} 已不存在。")

    arguments = json.loads(confirmation.arguments_json)
    tool_output = run_tool(tool.name, arguments, db=db)
    now = datetime.utcnow()

    confirmation.approver_user_id = approver.user_id
    confirmation.approver_api_key_name = approver.api_key_name
    confirmation.decision_reason = reason
    confirmation.decided_at = now
    confirmation.executed_at = now
    confirmation.result_json = json.dumps({"tool_output": tool_output}, ensure_ascii=False)
    confirmation.error = None if tool_output.get("ok") else str(tool_output.get("error"))
    confirmation.status = "executed" if tool_output.get("ok") else "failed"
    db.commit()
    db.refresh(confirmation)

    write_tool_audit_log(
        db=db,
        request_id=confirmation.request_id,
        auth=approver,
        tool=tool,
        allowed=True,
        reason=f"人工确认通过后执行：{reason}",
        arguments=arguments,
        result={
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_status": confirmation.status,
            "tool_output": tool_output,
        },
        error=confirmation.error,
    )
    return confirmation


def reject_confirmation(
    db: Session,
    confirmation_id: str,
    approver: AuthContext,
    reason: str,
) -> PendingConfirmation:
    # reject 只改变确认单状态，不执行工具。
    # 这能验证“未确认或被拒绝时，危险写操作不会发生”。
    if approver.role != "admin":
        raise HTTPException(status_code=403, detail="只有 admin 可以拒绝危险操作。")

    confirmation = get_confirmation_for_user(db, confirmation_id, approver)
    if confirmation.status != "pending":
        raise HTTPException(status_code=409, detail=f"确认单当前状态是 {confirmation.status}，不能重复拒绝。")

    confirmation.approver_user_id = approver.user_id
    confirmation.approver_api_key_name = approver.api_key_name
    confirmation.decision_reason = reason
    confirmation.decided_at = datetime.utcnow()
    confirmation.status = "rejected"
    confirmation.result_json = json.dumps({"rejected": True, "reason": reason}, ensure_ascii=False)
    db.commit()
    db.refresh(confirmation)

    tool = get_tool_definition(confirmation.tool_name)
    if tool is not None:
        write_tool_audit_log(
            db=db,
            request_id=confirmation.request_id,
            auth=approver,
            tool=tool,
            allowed=False,
            reason=f"人工确认拒绝：{reason}",
            arguments=json.loads(confirmation.arguments_json),
            result={"confirmation_id": confirmation.confirmation_id, "confirmation_status": "rejected"},
            error="危险操作被人工拒绝，未执行工具。",
        )
    return confirmation


def to_confirmation_response(confirmation: PendingConfirmation) -> ConfirmationResponse:
    # ORM Model 转 DTO。
    # 这样接口返回结构稳定，不会因为数据库字段调整而影响前端。
    return ConfirmationResponse(
        confirmation_id=confirmation.confirmation_id,
        request_id=confirmation.request_id,
        requester_user_id=confirmation.requester_user_id,
        requester_role=confirmation.requester_role,
        tool_name=confirmation.tool_name,
        tool_type=confirmation.tool_type,
        risk_level=confirmation.risk_level,
        arguments=json.loads(confirmation.arguments_json),
        status=confirmation.status,
        confirm_reason=confirmation.confirm_reason,
        approver_user_id=confirmation.approver_user_id,
        decision_reason=confirmation.decision_reason,
        result=json.loads(confirmation.result_json),
        error=confirmation.error,
        created_at=confirmation.created_at.isoformat(),
        decided_at=confirmation.decided_at.isoformat() if confirmation.decided_at else None,
        executed_at=confirmation.executed_at.isoformat() if confirmation.executed_at else None,
        expires_at=confirmation.expires_at.isoformat() if confirmation.expires_at else None
    )

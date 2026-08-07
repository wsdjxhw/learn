"""
confirmation.py —— 写操作确认单的"数据层"

职责：确认单（ConfirmationRequest 表）的增删改查。
只做"保存、查询、改状态"这些纯数据操作，不执行任何业务逻辑。

真正"批准后执行工具"的逻辑放在 tool_registry.py（执行中枢）里，
因为执行需要调用工具注册表，这里只负责管理确认单本身，避免循环依赖。
"""

import json
from datetime import datetime

from database import SessionLocal
from models import ConfirmationRequest
from sqlalchemy import select


def create_request(tool_name: str, args: dict, requested_by: str, requested_role: str) -> ConfirmationRequest:
    """创建一个 pending 状态的确认单，保存工具名和参数快照。

    参数快照的意义：审批人批准时，是严格按照"发起时的那份参数"执行，
    而不是审批时重新生成。这样即使中间有人改了数据，执行的都是当初
    想让对方确认的那份内容。
    """
    with SessionLocal() as db:
        req = ConfirmationRequest(
            tool_name=tool_name,
            args_json=json.dumps(args, ensure_ascii=False),
            requested_by=requested_by,
            requested_role=requested_role,
            status="pending",
        )
        db.add(req)
        db.commit()
        db.refresh(req)  # 刷新拿到数据库自动生成的自增 id
        return req


def list_requests(status: str | None = None) -> list[ConfirmationRequest]:
    """列出确认单，可以按状态过滤。最新的排前面。"""
    with SessionLocal() as db:
        stmt = select(ConfirmationRequest).order_by(ConfirmationRequest.id.desc())
        if status:
            stmt = stmt.where(ConfirmationRequest.status == status)
        return list(db.scalars(stmt).all())


def get_request(request_id: int) -> ConfirmationRequest | None:
    """按 id 取一条确认单，不存在返回 None。"""
    with SessionLocal() as db:
        return db.get(ConfirmationRequest, request_id)


def mark_status(
    request_id: int,
    new_status: str,
    decided_by: str,
    result_summary: str | None = None,
    error: str | None = None,
):
    """修改确认单状态：executed / rejected / failed，并记录审批人。

    这里单独用一个函数封装"改状态 + 写审批信息"，避免在每个接口里
    重复这段逻辑，也保证状态流转只在这一处发生。
    """
    with SessionLocal() as db:
        req = db.get(ConfirmationRequest, request_id)
        if req is None:
            return None
        req.status = new_status
        req.decided_by = decided_by
        req.decided_at = datetime.now()
        if result_summary is not None:
            req.result_summary = result_summary
        if error is not None:
            req.error = error
        db.commit()
        db.refresh(req)
        return req

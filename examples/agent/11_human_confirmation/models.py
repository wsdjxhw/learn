from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ToolAuditLog(Base):
    # ToolAuditLog 记录工具权限判断和执行结果。
    # 真实 Agent 项目里，工具调用通常会影响外部系统，所以“谁在什么时候调用了什么工具”必须可追踪。
    __tablename__ = "tool_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    api_key_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    tool_type: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PendingConfirmation(Base):
    # PendingConfirmation 保存“已经通过权限检查，但还不能立刻执行”的危险操作。
    # Java 类比：它像一个待审批单 Entity，不是工具结果本身。
    #
    # 真实项目中，删除数据、修改套餐、发邮件、付款等操作通常都要先生成确认单。
    # 用户或管理员确认后，系统才真正调用工具执行。
    __tablename__ = "pending_confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    confirmation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    requester_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    requester_api_key_name: Mapped[str] = mapped_column(String(64), nullable=False)
    requester_role: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    tool_type: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="pending")
    confirm_reason: Mapped[str] = mapped_column(Text, nullable=False)
    approver_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approver_api_key_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

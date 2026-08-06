from typing import Any, Literal

from pydantic import BaseModel, Field


UserRole = Literal["viewer", "operator", "admin"]
ToolType = Literal["read", "write", "admin"]
RiskLevel = Literal["low", "medium", "high"]
ConfirmationStatus = Literal["pending", "executed", "rejected", "failed"]
RecoveryAction = Literal["none", "retried", "fallback_used", "failed"]


class AuthContext(BaseModel):
    # AuthContext 是“当前调用者是谁”的 DTO。
    # 注意它不是 ORM Model，不对应数据库表，只是在接口和业务函数之间传递认证结果。
    user_id: str
    api_key_name: str
    role: UserRole


class PermissionResult(BaseModel):
    # 权限判断也要结构化，而不是只返回 True/False。
    # 这样前端、日志和排查问题时都能看到为什么允许或拒绝。
    allowed: bool
    reason: str


class ToolInfo(BaseModel):
    name: str
    description: str
    tool_type: ToolType
    risk_level: RiskLevel
    allowed_roles: list[UserRole]
    requires_confirmation: bool
    timeout_seconds: float
    max_retries: int
    fallback_tool_name: str | None
    expose_to_model: bool
    enabled: bool
    is_allowed_for_current_user: bool
    permission_reason: str


class ConfirmationResponse(BaseModel):
    # ConfirmationResponse 是待确认操作返回给前端的 DTO。
    # 它不直接暴露 ORM 的所有字段，只暴露前端和学习者需要理解的状态。
    confirmation_id: str
    request_id: str
    requester_user_id: str
    requester_role: str
    tool_name: str
    tool_type: str
    risk_level: str
    arguments: dict[str, Any]
    status: ConfirmationStatus
    confirm_reason: str
    approver_user_id: str | None
    decision_reason: str | None
    result: dict[str, Any]
    error: str | None
    created_at: str
    decided_at: str | None
    executed_at: str | None
    expires_at: str | None


class ConfirmationApproveRequest(BaseModel):
    # approve 接口的请求体。
    # reason 用来说明为什么允许执行这次危险操作，真实项目里这是审计必备字段。
    reason: str = Field(min_length=1, description="批准执行的原因。")


class ConfirmationRejectRequest(BaseModel):
    # reject 接口的请求体。
    # 拒绝也要写原因，避免后续只看到状态却不知道业务判断依据。
    reason: str = Field(min_length=1, description="拒绝执行的原因。")


class ToolRunRequest(BaseModel):
    # 手动执行工具的请求体 DTO。
    # arguments 用 dict，是因为不同工具需要的参数不同，统一成一个字段更适合教学演示。
    tool_name: str = Field(min_length=1, description="要执行的工具名称。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数，结构取决于具体工具。")


class ToolRunResponse(BaseModel):
    request_id: str
    auth: AuthContext
    tool_name: str
    allowed: bool
    permission_reason: str
    tool_output: dict[str, Any]
    requires_confirmation: bool = False
    confirmation: ConfirmationResponse | None = None


class ToolAttemptResponse(BaseModel):
    # ToolAttemptResponse 表示一次工具尝试。
    # 真实项目排查工具问题时，不能只知道“最后失败”，还要知道每次尝试怎么失败。
    attempt: int
    tool_name: str
    ok: bool
    elapsed_ms: int
    error_code: str | None
    error: str | None
    retryable: bool
    will_retry: bool


class RecoveryPreviewRequest(BaseModel):
    # 这个 DTO 用来专门练习失败恢复，不经过 Agent 自动决策。
    # arguments 里可以传 simulate_failure=timeout/transient/permanent 来稳定复现故障。
    tool_name: str = Field(min_length=1, description="要执行并观察恢复策略的工具名称。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数，可加入 simulate_failure 复现故障。")


class RecoveryPreviewResponse(BaseModel):
    request_id: str
    auth: AuthContext
    tool_name: str
    recovery_action: RecoveryAction
    tool_output: dict[str, Any]
    attempts: list[ToolAttemptResponse]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="用户本轮输入。")
    allow_tool: bool = Field(default=True, description="是否允许 Agent 使用工具，用来对比纯回答和工具调用。")


class ChatResponse(BaseModel):
    reply: str
    auth: AuthContext
    used_tool: bool
    tool_name: str | None
    tool_output: dict[str, Any] | None
    requires_confirmation: bool = False
    confirmation: ConfirmationResponse | None = None
    steps: list[dict[str, Any]]


class AuditLogResponse(BaseModel):
    id: int
    request_id: str
    user_id: str
    api_key_name: str
    role: str
    tool_name: str
    tool_type: str
    risk_level: str
    allowed: bool
    reason: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    error: str | None
    created_at: str

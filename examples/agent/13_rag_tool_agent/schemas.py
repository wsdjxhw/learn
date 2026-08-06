from typing import Any, Literal

from pydantic import BaseModel, Field


UserRole = Literal["viewer", "operator", "admin"]
ToolType = Literal["read", "write", "admin"]
RiskLevel = Literal["low", "medium", "high"]


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
    # ToolInfo 是工具清单返回给前端的 DTO，只暴露前端需要的信息。
    name: str
    description: str
    tool_type: ToolType
    risk_level: RiskLevel
    allowed_roles: list[UserRole]
    expose_to_model: bool
    enabled: bool
    is_allowed_for_current_user: bool
    permission_reason: str


class DocumentCreate(BaseModel):
    # 文档录入的请求 DTO。
    # Java 类比：类似 CreateDocumentRequest。
    # chunk_size 和 overlap 是 RAG 切分的参数，初学者可以先不改，用默认值。
    title: str = Field(min_length=1, description="文档标题，例如：公司报销制度。")
    content: str = Field(min_length=1, description="文档正文，会被切成多个 chunk。")
    chunk_size: int = Field(default=300, ge=50, description="每个片段大约多少字符。")
    overlap: int = Field(default=50, ge=0, description="相邻片段重叠多少字符，避免句子被切断。")


class ToolRunRequest(BaseModel):
    # 手动执行工具的请求体 DTO。
    # arguments 用 dict，是因为不同工具需要的参数不同，统一成一个字段更适合教学演示。
    tool_name: str = Field(min_length=1, description="要执行的工具名称，本模块只有 search_documents。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数，结构取决于具体工具。")


class ToolRunResponse(BaseModel):
    # 手动执行工具后的响应 DTO。
    # sources 是从 tool_output.results 里抽出来的检索片段，前端可以直接展示“回答依据”。
    request_id: str
    auth: AuthContext
    tool_name: str
    allowed: bool
    permission_reason: str
    tool_output: dict[str, Any]
    sources: list[dict[str, Any]]


class ChatRequest(BaseModel):
    # 用户向 Agent 提问的请求体 DTO。
    # allow_tool=false 时 Agent 不能用检索工具，用来对比“能检索”和“不能检索”的回答差异。
    message: str = Field(min_length=1, description="用户本轮输入。")
    allow_tool: bool = Field(default=True, description="是否允许 Agent 使用检索工具。")


class ChatResponse(BaseModel):
    # Agent 完整响应的 DTO。
    # sources 是本模块核心字段：告诉前端和用户“这个回答依据了哪些资料”。
    reply: str
    auth: AuthContext
    used_tool: bool
    tool_name: str | None
    tool_output: dict[str, Any] | None
    sources: list[dict[str, Any]]
    steps: list[dict[str, Any]]


class AuditLogResponse(BaseModel):
    # 审计日志 DTO，只暴露前端需要看的字段，不直接暴露 ORM 对象。
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

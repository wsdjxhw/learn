import json
import uuid
from typing import Any

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from models import ToolAuditLog
from schemas import AuthContext, PermissionResult
from settings import get_settings
from tool_registry import ToolDefinition


def get_current_auth(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> AuthContext:
    # 这是认证依赖函数。
    # FastAPI 会从请求头 X-API-Key 里取值，然后把返回的 AuthContext 注入到接口函数。
    #
    # 教学版为了开箱可跑：如果请求没带 X-API-Key，就默认使用 learner-key。
    # 真实项目不能这样做，通常缺少 API Key 会直接返回 401。
    settings = get_settings()
    api_key = x_api_key or settings.learner_api_key

    profiles = {
        settings.learner_api_key: AuthContext(user_id="u_learner", api_key_name="learner-key", role="viewer"),
        settings.operator_api_key: AuthContext(user_id="u_operator", api_key_name="operator-key", role="operator"),
        settings.admin_api_key: AuthContext(user_id="u_admin", api_key_name="admin-key", role="admin"),
    }

    auth = profiles.get(api_key)
    if auth is None:
        # 401 表示“你是谁还没通过认证”。
        # 403 才表示“知道你是谁，但你没有权限做这件事”。
        raise HTTPException(status_code=401, detail="无效的 X-API-Key。请使用 .env.example 中的教学 API Key。")

    return auth


def check_tool_permission(
    auth: AuthContext,
    tool: ToolDefinition,
    arguments: dict[str, Any] | None = None,
) -> PermissionResult:
    # 权限检查必须在后端执行，不能只相信模型看到的工具 schema。
    # 模型可能被 prompt injection 诱导，也可能生成未授权工具名。
    #
    # 本模块对比模块 12 做了简化：
    # - 只有 search_documents 一个读工具，且三个角色都能用，所以这里主要是 enabled 和角色检查。
    # - 模块 12 的资源级权限（target_user_id）和敏感关键词过滤，本模块暂时不需要。
    #   等模块 14 做生产级 RAG 时，会补上“文档级权限隔离”，让不同用户只能检索到有权限的文档。
    if not tool.enabled:
        return PermissionResult(allowed=False, reason=f"工具 {tool.name} 当前已停用。")

    if auth.role not in tool.allowed_roles:
        return PermissionResult(
            allowed=False,
            reason=f"当前角色 {auth.role} 不能调用 {tool.name}，允许角色为 {list(tool.allowed_roles)}。",
        )

    return PermissionResult(allowed=True, reason="权限检查通过。")


def new_request_id() -> str:
    # request_id 用来把一次工具调用和审计日志关联起来。
    # uuid4() 会生成随机 ID，适合教学示例和多数业务日志场景。
    return uuid.uuid4().hex


def write_tool_audit_log(
    db: Session,
    request_id: str,
    auth: AuthContext,
    tool: ToolDefinition,
    allowed: bool,
    reason: str,
    arguments: dict[str, Any],
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> ToolAuditLog:
    # 审计日志必须在权限拒绝时也记录。
    # 否则真实项目里只能看到成功调用，看不到越权尝试。
    log = ToolAuditLog(
        request_id=request_id,
        user_id=auth.user_id,
        api_key_name=auth.api_key_name,
        role=auth.role,
        tool_name=tool.name,
        tool_type=tool.tool_type,
        risk_level=tool.risk_level,
        allowed=allowed,
        reason=reason,
        arguments_json=json.dumps(arguments, ensure_ascii=False),
        result_json=json.dumps(result or {}, ensure_ascii=False),
        error=error,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

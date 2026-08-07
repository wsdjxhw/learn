"""
main.py —— FastAPI 接口层（HTTP 入口）

职责：定义所有 HTTP 接口，把"网络请求"翻译成"业务调用"。
main.py 本身几乎不写业务逻辑，业务在 agent.py / tool_registry.py 里。

分层原因（重要）：
  main.py          HTTP 层：谁来的、请求长什么样、返回什么格式
  agent.py         流程层：Agent 循环怎么转
  tool_registry.py 执行层：工具怎么执行、怎么确认、怎么审计
  查询/写工具      数据层：真正操作数据库
  分开的好处：换接口（比如改成 gRPC）只动 main.py，改业务只动业务文件。

启动：uvicorn main:app --reload
文档：启动后访问 http://127.0.0.1:8000/docs 可以直接点按钮测试接口。
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

import confirmation
from agent import run_agent
from database import get_db, init_db
from models import DatabaseOpLog
from provider import get_provider
from schemas import (
    AuditLogOut,
    ChatRequest,
    ChatResponse,
    ConfirmationOut,
    ToolInfo,
    ToolRunRequest,
    ToolRunResponse,
    serialize_audit_log,
    serialize_confirmation,
)
from seed import seed_if_empty
from security import UserContext, get_current_user, has_role
from tool_registry import (
    approve_confirmation,
    execute_tool,
    reject_confirmation,
    visible_tools_for_role,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动时自动建表 + 写入 demo 数据（相当于程序的准备工作）。"""
    init_db()
    seed_if_empty()
    yield


app = FastAPI(
    title="数据库工具智能体",
    description="让 Agent 用自然语言查询和修改数据库，写操作必须人工确认，所有操作可审计。",
    lifespan=lifespan,
)


def require_operator(user: UserContext = Depends(get_current_user)) -> UserContext:
    """依赖注入：要求当前用户至少是 operator 角色，否则返回 403。

    用法：在接口参数里写 `user=Depends(require_operator)`，
    接口执行前会先做这次权限检查。
    """
    if not has_role("operator", user.role):
        raise HTTPException(status_code=403, detail=f"角色 {user.role} 无权访问该接口，需要 operator 及以上")
    return user


@app.get("/")
def root():
    """根路径：列一下都有哪些接口，方便新手照着测试。"""
    return {
        "app": "数据库工具智能体",
        "接口列表": {
            "GET  /tools": "查看当前角色可见的工具",
            "POST /agent/chat": "用自然语言让 Agent 查询/修改数据库",
            "POST /tool/run": "手动执行某个工具（看权限/校验/确认门）",
            "GET  /confirmations": "查看确认单（写操作等待审批）",
            "POST /confirmations/{id}/approve": "批准确认单 -> 真正执行写操作",
            "POST /confirmations/{id}/reject": "拒绝确认单 -> 不执行",
            "GET  /audit-logs": "查看审计日志（所有数据库操作，可追溯）",
        },
        "请求头": {"X-API-Key": "sk-viewer-0000000001 / sk-operator-0000000001 / sk-admin-0000000001"},
    }


@app.get("/tools", response_model=list[ToolInfo])
def list_tools(user: UserContext = Depends(get_current_user)):
    """返回当前角色可见的工具。不同角色看到的工具数量不同（权限白名单）。"""
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            min_role=t.min_role,
            risk=t.risk,
            is_write=t.is_write,
            requires_confirmation=t.requires_confirmation,
        )
        for t in visible_tools_for_role(user.role)
    ]


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(req: ChatRequest, user: UserContext = Depends(get_current_user)):
    """核心接口：用户对数据库助手说一句话，Agent 自动选工具、执行、回答。

    参数来源说明：
      req   来自请求体（JSON body）
      user  来自请求头 X-API-Key（依赖注入）
    """
    provider = get_provider()
    return run_agent(req.question, user, provider)


@app.post("/tool/run", response_model=ToolRunResponse)
def tool_run(req: ToolRunRequest, user: UserContext = Depends(get_current_user)):
    """手动执行一个工具（绕过 Agent，直接看工具本身的行为）。

    用处：测试某个工具的参数校验、确认门、业务规则时很方便。
    注意：写工具在这里同样会进入"确认门"，不会直接执行。
    """
    result = execute_tool(req.tool_name, req.args, user.role, user.api_key)
    return ToolRunResponse(
        status=result.status,
        message=result.message,
        data=result.data,
        confirmation_id=result.confirmation_id,
    )


@app.get("/confirmations", response_model=list[ConfirmationOut])
def list_confirmations(
    status: str | None = Query(default=None, description="按状态过滤：pending/executed/rejected/failed"),
    user: UserContext = Depends(require_operator),  # 只有 operator 及以上能看审批队列
):
    """查看确认单列表。pending 的就是等待审批的写操作。"""
    reqs = confirmation.list_requests(status)
    return [serialize_confirmation(r) for r in reqs]


@app.post("/confirmations/{confirmation_id}/approve", response_model=dict)
def approve(
    confirmation_id: int,
    user: UserContext = Depends(require_operator),
):
    """批准确认单：按快照参数真正执行写操作。

    这是"写入必须确认"的关键一步：只有走到这里，写操作才会真正发生。
    """
    result, req = approve_confirmation(confirmation_id, user.role, user.api_key)
    return {
        "execution": ToolRunResponse(
            status=result.status,
            message=result.message,
            data=result.data,
            confirmation_id=result.confirmation_id,
        ).model_dump(),
        "confirmation": serialize_confirmation(req),
    }


@app.post("/confirmations/{confirmation_id}/reject", response_model=ConfirmationOut)
def reject(
    confirmation_id: int,
    user: UserContext = Depends(require_operator),
):
    """拒绝确认单：不执行，标记为 rejected 并写审计。"""
    req = reject_confirmation(confirmation_id, user.role, user.api_key)
    return serialize_confirmation(req)


@app.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    tool_name: str | None = Query(default=None, description="按工具名过滤"),
    user: UserContext = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """查看审计日志：每一次数据库操作尝试（成功/拦截/拒绝/失败都记）。

    这是"所有数据库操作可追踪"的落地接口。
    真实项目里审计日志通常还要支持时间范围、角色、模糊搜索、导出等。
    """
    stmt = select(DatabaseOpLog).order_by(DatabaseOpLog.id.desc()).limit(limit)
    if tool_name:
        stmt = stmt.where(DatabaseOpLog.tool_name == tool_name)
    logs = list(db.scalars(stmt).all())
    return [serialize_audit_log(l) for l in logs]

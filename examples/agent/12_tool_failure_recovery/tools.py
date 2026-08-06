import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ToolAuditLog
from tool_registry import get_tool_definition


class ToolExecutionError(Exception):
    """工具执行失败时主动抛出的错误。"""


def _simulate_teaching_failure(arguments: dict[str, Any]) -> dict[str, Any] | None:
    # 这个函数专门用于教学，稳定复现“外部工具不可靠”的场景。
    # 真实项目里，超时和短暂失败来自 HTTP 请求、数据库连接、第三方服务等外部依赖。
    #
    # _attempt 由 recovery.py 注入，表示当前是第几次尝试。
    # 初学者要注意：用户请求体里不需要传 _attempt，这是执行器内部补的参数。
    simulate_failure = str(arguments.get("simulate_failure", "none")).lower()
    attempt = int(arguments.get("_attempt", 1))
    fail_times = int(arguments.get("fail_times", 1))

    if simulate_failure in {"", "none"}:
        return None

    if simulate_failure == "timeout":
        return {
            "ok": False,
            "error_code": "timeout",
            "error": "模拟外部工单系统超时。",
            "retryable": True,
        }

    if simulate_failure == "transient" and attempt <= fail_times:
        return {
            "ok": False,
            "error_code": "transient_error",
            "error": f"模拟短暂故障：第 {attempt} 次失败。",
            "retryable": True,
        }

    if simulate_failure == "permanent":
        return {
            "ok": False,
            "error_code": "permanent_error",
            "error": "模拟永久失败：参数或业务条件无法满足。",
            "retryable": False,
        }

    return None


def get_user_plan(target_user_id: str) -> dict[str, Any]:
    # 读工具：只查询资料，不修改业务状态。
    # 教学版用固定字典模拟用户套餐，后续 RAG 工具 Agent 会替换成真实检索。

    user_plan = {
        "user_id": target_user_id,
        "plan": "basic",
        "features": ["basic_features"],
    }
    return {"ok": True, "user_plan": user_plan}


def search_company_policy(keyword: str) -> dict[str, Any]:
    # 读工具：只查询资料，不修改业务状态。
    # 教学版用固定字典模拟制度库，后续 RAG 工具 Agent 会替换成真实检索。
    policies = {
        "报销": "差旅报销需要在行程结束后 7 天内提交发票和审批单。",
        "假期": "年假需要至少提前 3 个工作日申请，病假需要补充证明材料。",
        "密码": "内部系统密码至少 12 位，并且不能和最近 3 次密码重复。",
        "退款": "订单支付后 24 小时内可以原路退款，超过 24 小时需要人工审核。",
        "薪酬": "员工薪酬根据岗位和经验计算，不能直接修改。",
    }
    # 敏感关键词（薪酬）的权限由 permissions.check_tool_permission 统一判断，
    # 工具本身不重复检查——两处判断一旦不一致就会产生绕过。
    matches = []
    for policy_keyword, content in policies.items():
        if keyword in policy_keyword or policy_keyword in keyword:
            matches.append({"keyword": policy_keyword, "content": content, "source": f"policy:{policy_keyword}"})

    if not matches:
        raise ToolExecutionError(f"没有找到和 {keyword} 相关的制度。")

    return {"query": keyword, "matches": matches}


def get_memory_summary(target_user_id: str, topic: str) -> dict[str, Any]:
    # 中风险读工具：它不写数据，但可能读取用户画像。
    # 这里不直接复用上一模块数据库，避免学习者为了本节被迫读完整记忆治理代码。
    mock_memories = {
        "u_learner": {"偏好": "喜欢先看接口输入输出，再读核心函数。", "限制": "Python 基础不扎实，需要教学型注释。"},
        "u_operator": {"偏好": "关注工单处理效率。", "画像": "运营同学，需要处理用户问题。"},
        "u_admin": {"偏好": "关注权限、审计和风险控制。", "画像": "系统管理员。"},
    }

    summary = mock_memories.get(target_user_id)
    if summary is None:
        raise ToolExecutionError(f"没有找到用户 {target_user_id} 的教学版记忆摘要。")

    matched = {key: value for key, value in summary.items() if topic in key or key in topic}
    return {"target_user_id": target_user_id, "topic": topic, "summary": matched or summary}


def create_support_ticket(target_user_id: str, title: str, priority: str = "normal") -> dict[str, Any]:
    # 写工具：它代表“向业务系统创建一条工单”。
    # 教学版不额外建 tickets 表，而是用返回值和审计日志展示写入动作。
    normalized_priority = priority.lower()
    if normalized_priority not in {"low", "normal", "high"}:
        raise ToolExecutionError("priority 只能是 low、normal 或 high。")

    if len(title.strip()) < 4:
        raise ToolExecutionError("title 太短，真实工单需要能说明问题。")

    ticket_seed = f"{target_user_id}:{title}:{normalized_priority}"
    ticket_id = "TICKET-" + str(abs(hash(ticket_seed)))[:8]
    return {
        "ticket_id": ticket_id,
        "target_user_id": target_user_id,
        "title": title,
        "priority": normalized_priority,
        "status": "created",
    }


def create_support_ticket_fallback(
    target_user_id: str,
    title: str,
    priority: str = "normal",
    original_error: str = "",
) -> dict[str, Any]:
    # 降级工具：主工单系统不可用时，不让整个 Agent 接口崩溃。
    # 教学版用“写入人工处理队列”的返回值模拟真实降级。
    # 真实项目中这里可能写入数据库、消息队列或发送告警。
    fallback_seed = f"fallback:{target_user_id}:{title}:{priority}:{original_error}"
    fallback_id = "FALLBACK-" + str(abs(hash(fallback_seed)))[:8]
    return {
        "fallback_id": fallback_id,
        "target_user_id": target_user_id,
        "title": title,
        "priority": priority,
        "status": "queued_for_manual_retry",
        "original_error": original_error,
    }


def update_user_plan(target_user_id: str, new_plan: str, reason: str) -> dict[str, Any]:
    # 高风险写工具：修改套餐会影响计费、权限或商业权益。
    # 本模块新增人工确认：这个函数只会在 approve 之后被调用。
    # 也就是说，函数里返回的 updated_in_teaching_mock 代表“确认后执行”，不是用户一请求就执行。
    normalized_plan = new_plan.lower()
    if normalized_plan not in {"free", "pro", "enterprise"}:
        raise ToolExecutionError("new_plan 只能是 free、pro 或 enterprise。")

    if len(reason.strip()) < 4:
        raise ToolExecutionError("修改套餐必须提供明确原因。")

    return {
        "target_user_id": target_user_id,
        "new_plan": normalized_plan,
        "status": "updated_after_human_confirmation",
        "reason": reason,
    }


def list_audit_logs(db: Session, limit: int = 10) -> dict[str, Any]:
    # 管理员工具：读取最近工具调用日志。
    # select() 是 SQLAlchemy 查询语句，类似 SQL: SELECT * FROM tool_audit_logs ORDER BY id DESC LIMIT ?。
    safe_limit = max(1, min(int(limit), 50))
    rows = db.execute(select(ToolAuditLog).order_by(ToolAuditLog.id.desc()).limit(safe_limit)).scalars().all()
    return {
        "logs": [
            {
                "id": row.id,
                "request_id": row.request_id,
                "user_id": row.user_id,
                "role": row.role,
                "tool_name": row.tool_name,
                "allowed": row.allowed,
                "reason": row.reason,
                "arguments": json.loads(row.arguments_json),
                "error": row.error,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


def run_tool(tool_name: str, arguments: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
    # run_tool 是唯一的工具执行入口。
    # 真实项目里不要让模型传一个函数名后直接 globals()[name](**args)，那会变成安全漏洞。
    if get_tool_definition(tool_name) is None:
        return {
            "ok": False,
            "tool_name": tool_name,
            "error_code": "unknown_tool",
            "error": f"未知工具：{tool_name}",
            "retryable": False,
        }

    try:
        if tool_name == "get_user_plan":
            result = get_user_plan(target_user_id=str(arguments.get("target_user_id", "")))
        elif tool_name == "search_company_policy":
            result = search_company_policy(keyword=str(arguments.get("keyword", "")))
        elif tool_name == "get_memory_summary":
            result = get_memory_summary(
                target_user_id=str(arguments.get("target_user_id", "")),
                topic=str(arguments.get("topic", "偏好")),
            )
        elif tool_name == "create_support_ticket":
            simulated = _simulate_teaching_failure(arguments)
            if simulated is not None:
                return {"tool_name": tool_name, **simulated}
            result = create_support_ticket(
                target_user_id=str(arguments.get("target_user_id", "")),
                title=str(arguments.get("title", "")),
                priority=str(arguments.get("priority", "normal")),
            )
        elif tool_name == "create_support_ticket_fallback":
            result = create_support_ticket_fallback(
                target_user_id=str(arguments.get("target_user_id", "")),
                title=str(arguments.get("title", "")),
                priority=str(arguments.get("priority", "normal")),
                original_error=str(arguments.get("original_error", "")),
            )
        elif tool_name == "update_user_plan":
            result = update_user_plan(
                target_user_id=str(arguments.get("target_user_id", "")),
                new_plan=str(arguments.get("new_plan", "")),
                reason=str(arguments.get("reason", "")),
            )
        elif tool_name == "list_audit_logs":
            if db is None:
                raise ToolExecutionError("list_audit_logs 需要数据库会话。")
            result = list_audit_logs(db=db, limit=int(arguments.get("limit", 10)))
        else:
            return {
                "ok": False,
                "tool_name": tool_name,
                "error_code": "not_implemented",
                "error": f"未实现工具：{tool_name}",
                "retryable": False,
            }

        return {"ok": True, "tool_name": tool_name, "result": result}
    except (TypeError, ValueError) as exc:
        return {
            "ok": False,
            "tool_name": tool_name,
            "error_code": "bad_arguments",
            "error": f"工具参数格式错误：{exc}",
            "retryable": False,
        }
    except ToolExecutionError as exc:
        return {
            "ok": False,
            "tool_name": tool_name,
            "error_code": "tool_execution_error",
            "error": str(exc),
            "retryable": False,
        }

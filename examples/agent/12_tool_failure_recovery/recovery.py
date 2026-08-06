import time
from typing import Any

from sqlalchemy.orm import Session

from schemas import AuthContext
from tool_registry import ToolDefinition, get_tool_definition
from tools import run_tool


def build_failure_explanation(tool_name: str, output: dict[str, Any], attempts: list[dict[str, Any]]) -> str:
    # 失败解释不能只返回“error”。
    # 真实产品里，用户和前端需要知道：失败是否可重试、系统做过几次尝试、下一步建议是什么。
    error_code = output.get("error_code", "unknown")
    error = output.get("error", "未知错误")
    attempt_count = len(attempts)

    if error_code == "timeout":
        return f"{tool_name} 调用超时，系统已尝试 {attempt_count} 次。建议稍后重试或走人工处理。原始错误：{error}"

    if error_code == "transient_error":
        return f"{tool_name} 遇到短暂故障，系统已尝试 {attempt_count} 次。若仍失败，建议稍后重试。原始错误：{error}"

    if error_code == "permanent_error":
        return f"{tool_name} 遇到不可自动恢复的业务错误，继续重试通常无效。请检查参数或改走人工处理。原始错误：{error}"

    return f"{tool_name} 执行失败，系统已尝试 {attempt_count} 次。错误：{error}"


def _attempt_record(
    attempt: int,
    tool_name: str,
    elapsed_ms: int,
    output: dict[str, Any],
    will_retry: bool,
) -> dict[str, Any]:
    # 每次尝试都返回结构化记录，方便前端展示 steps，也方便排查。
    return {
        "attempt": attempt,
        "tool_name": tool_name,
        "ok": bool(output.get("ok")),
        "elapsed_ms": elapsed_ms,
        "error_code": output.get("error_code"),
        "error": output.get("error"),
        "retryable": bool(output.get("retryable", False)),
        "will_retry": will_retry,
    }


def _timeout_output(tool: ToolDefinition, requested_delay_seconds: float) -> dict[str, Any]:
    # 教学版超时判断。
    # 真实项目里通常由 HTTP 客户端、数据库驱动或异步任务框架来强制取消超时请求。
    # 这里不真的 sleep，是为了让示例运行很快，同时能看懂 timeout_seconds 的作用。
    return {
        "ok": False,
        "tool_name": tool.name,
        "error_code": "timeout",
        "error": (
            f"工具预计耗时 {requested_delay_seconds} 秒，超过配置的 "
            f"timeout_seconds={tool.timeout_seconds} 秒。"
        ),
        "retryable": True,
    }


def _fallback_arguments(arguments: dict[str, Any], original_output: dict[str, Any]) -> dict[str, Any]:
    # 降级工具通常不需要所有原始参数。
    # 这里保留工单核心字段，并把主工具失败原因作为 original_error 传给降级工具。
    return {
        "target_user_id": str(arguments.get("target_user_id", "")),
        "title": str(arguments.get("title", "")),
        "priority": str(arguments.get("priority", "normal")),
        "original_error": str(original_output.get("error", "主工具失败")),
    }


def execute_tool_with_recovery(
    db: Session,
    auth: AuthContext,
    tool: ToolDefinition,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    # 这是本模块的核心执行器。
    # Java 类比：它像一个带重试和降级策略的 ToolService，不是具体工具本身。
    #
    # tools.py 的 run_tool() 只负责“执行一次”；
    # recovery.py 负责“失败后怎么办”：重试、降级、解释失败。
    attempts: list[dict[str, Any]] = []
    max_attempts = tool.max_retries + 1
    used_retry = False

    last_output: dict[str, Any] = {
        "ok": False,
        "tool_name": tool.name,
        "error_code": "not_started",
        "error": "工具尚未执行。",
        "retryable": False,
    }

    for attempt in range(1, max_attempts + 1):
        # dict(arguments) 表示复制一份参数，避免修改原始请求体。
        # _attempt 是执行器内部参数，帮助 mock 工具判断第几次尝试。
        attempt_arguments = dict(arguments)
        attempt_arguments["_attempt"] = attempt

        started_at = time.perf_counter()
        requested_delay_seconds = float(attempt_arguments.get("requested_delay_seconds", 0) or 0)
        if requested_delay_seconds > tool.timeout_seconds:
            output = _timeout_output(tool, requested_delay_seconds)
        else:
            output = run_tool(tool.name, attempt_arguments, db=db)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        last_output = output

        retryable = bool(output.get("retryable", False))
        will_retry = (not output.get("ok")) and retryable and attempt < max_attempts
        if will_retry:
            used_retry = True

        attempts.append(_attempt_record(attempt, tool.name, elapsed_ms, output, will_retry))

        if output.get("ok"):
            return {
                **output,
                "attempts": attempts,
                "recovery_action": "retried" if used_retry else "none",
                "fallback_used": False,
                "final_tool_name": tool.name,
                "failure_explanation": None,
            }

        if not will_retry:
            break

    fallback_output: dict[str, Any] | None = None
    # 只有 retryable 错误才进入降级。
    # 例如超时、短暂网络故障可以转人工队列；但参数错误、业务规则不允许这类 permanent error
    # 不应该被包装成“降级成功”，否则会掩盖真正的问题。
    if tool.fallback_tool_name and last_output.get("retryable"):
        fallback_tool = get_tool_definition(tool.fallback_tool_name)
        if fallback_tool is not None:
            fallback_args = _fallback_arguments(arguments, last_output)
            started_at = time.perf_counter()
            fallback_output = run_tool(fallback_tool.name, fallback_args, db=db)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            attempts.append(
                _attempt_record(
                    attempt=len(attempts) + 1,
                    tool_name=fallback_tool.name,
                    elapsed_ms=elapsed_ms,
                    output=fallback_output,
                    will_retry=False,
                )
            )

            if fallback_output.get("ok"):
                return {
                    "ok": True,
                    "tool_name": tool.name,
                    "final_tool_name": fallback_tool.name,
                    "fallback_used": True,
                    "recovery_action": "fallback_used",
                    "result": fallback_output["result"],
                    "attempts": attempts,
                    "failure_explanation": build_failure_explanation(tool.name, last_output, attempts),
                    "original_error": last_output.get("error"),
                    "original_error_code": last_output.get("error_code"),
                }

    return {
        **last_output,
        "attempts": attempts,
        "recovery_action": "failed",
        "fallback_used": False,
        "final_tool_name": tool.name,
        "failure_explanation": build_failure_explanation(tool.name, last_output, attempts),
    }

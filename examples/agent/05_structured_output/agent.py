from typing import Any

from parser import compact_error, parse_and_validate
from provider import generate_model_text
from schemas import RefundDecision


def _fallback_decision(case: dict[str, Any], reason: str) -> dict[str, Any]:
    # 降级结果也要符合 RefundDecision。
    # 这点很关键：即使模型输出坏了，接口也应该返回稳定结构，前端和后续服务才不会一起崩。
    fallback = RefundDecision(
        decision_type="manual_review",
        category="refund",
        priority="medium",
        summary=f"模型结构化输出失败，原始请求：{case.get('message', '')}",
        missing_fields=[],
        risk_flags=["structured_output_failed"],
        confidence=0,
        action={
            "tool_name": "manual_review",
            "arguments": {
                "message": case.get("message"),
                "order_amount": case.get("order_amount"),
                "days_since_purchase": case.get("days_since_purchase"),
                "item_problem": case.get("item_problem"),
            },
            "reason": reason,
        },
        user_visible_answer="系统暂时无法自动生成可靠结论，已转人工审核。",
    )
    return fallback.model_dump()


def _user_debug_message(parse_result: dict[str, Any]) -> str:
    # 练习三：把失败原因转成适合前端展示的文案。
    #
    # 为什么不直接返回 parse_result["error"]？
    # - error 可能是 Pydantic 的字段路径、完整异常对象或模型原始响应。
    # - 这些对前端用户没有意义，还可能泄露内部字段名、prompt 或服务响应体。
    # 这里用固定文案，让用户知道“发生了什么级别的问题”，但看不到内部细节。
    if parse_result["stage"] == "model_call":
        return "模型服务暂时不可用，请稍后再试。"
    if parse_result["stage"] == "json_parse":
        return "模型返回的内容无法被解析为 JSON，系统已尝试自动恢复。"
    if parse_result["stage"] == "pydantic_validation":
        return "模型返回的结构不符合约定，系统已尝试自动恢复。"
    return "系统已自动完成处理。"


def run_structured_agent(case: dict[str, Any]) -> dict[str, Any]:
    # 这是本模块的核心流程。
    #
    # 输入：
    # - case 来自 FastAPI 请求体，包含用户自然语言和订单字段。
    #
    # 处理：
    # - 调用 mock 或 DeepSeek 得到原始文本。
    # - 把文本解析成 JSON。
    # - 用 Pydantic 校验输出契约。
    # - 失败时最多重试一次。
    # - 仍失败时降级为人工审核，但返回结构仍然稳定。
    #
    # 输出：
    # - status 告诉调用方是一次成功、重试恢复，还是降级。
    # - decision 是已经通过契约校验的结构化结果。
    # - attempts 保留每次模型输出和错误，方便调试。
    allow_retry = bool(case.get("allow_retry", True))
    max_attempts = 2 if allow_retry else 1
    attempts: list[dict[str, Any]] = []
    previous_error: str | None = None

    for attempt_number in range(1, max_attempts + 1):
        try:
            raw_text = generate_model_text(case=case, previous_error=previous_error)
        except Exception as exc:
            # 真实模型调用也可能失败，例如密钥没配、网络超时、服务返回 500。
            # 这类错误不属于 JSON 解析失败，但对接口调用方来说仍然需要稳定返回。
            previous_error = f"模型调用失败：{exc}"
            attempts.append(
                {
                    "attempt_number": attempt_number,
                    "raw_output": None,
                    "ok": False,
                    "failed_stage": "model_call",
                    "error": previous_error,
                    "user_debug_message": _user_debug_message(
                        {"stage": "model_call"}
                    ),
                }
            )
            break

        parse_result = parse_and_validate(raw_text)
        attempts.append(
            {
                "attempt_number": attempt_number,
                "raw_output": raw_text,
                "ok": parse_result["ok"],
                "failed_stage": None if parse_result["ok"] else parse_result["stage"],
                "error": parse_result["error"],
                "user_debug_message": _user_debug_message(parse_result),
            }
        )

        if parse_result["ok"]:
            return {
                "status": "succeeded" if attempt_number == 1 else "recovered",
                "retry_used": attempt_number > 1,
                "decision": parse_result["data"],
                "attempts": attempts,
                "contract": {
                    "schema_name": "RefundDecision",
                    "important_rule": "后端只信任通过 Pydantic 校验后的 data，不直接信任 raw_output。",
                },
            }

        previous_error = compact_error(parse_result)

    return {
        "status": "degraded",
        "retry_used": allow_retry,
        "decision": _fallback_decision(case=case, reason=previous_error or "未知结构化输出错误。"),
        "attempts": attempts,
        "contract": {
            "schema_name": "RefundDecision",
            "important_rule": "降级结果也符合同一份输出契约，调用方不用为坏输出写特殊分支。",
        },
    }

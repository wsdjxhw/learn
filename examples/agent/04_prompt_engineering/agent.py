from datetime import datetime
from typing import Any

from mock_model import decide_actions
from prompt_store import load_prompt
from tools import run_tool


def resolve_argument_value(value: Any, step_outputs: dict[str, dict[str, Any]]) -> Any:
    # 复用上一模块学过的数据传递思想。
    # 如果参数写成 {"from_step": "policy", "field": "policy"}，
    # 就表示从 policy 步骤的输出里取 policy 字段。
    if isinstance(value, dict) and "from_step" in value and "field" in value:
        return step_outputs[value["from_step"]][value["field"]]

    if isinstance(value, dict):
        return {
            key: resolve_argument_value(inner_value, step_outputs)
            for key, inner_value in value.items()
        }

    return value


def resolve_arguments(
    raw_arguments: dict[str, Any],
    step_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        name: resolve_argument_value(value, step_outputs)
        for name, value in raw_arguments.items()
    }


def run_agent_with_prompt(case: dict[str, Any], prompt_version: str) -> dict[str, Any]:
    # 这是本模块的核心函数。
    #
    # 输入：
    # - case：来自 FastAPI 请求体，包含用户问题和订单信息。
    # - prompt_version：来自请求体或 .env，决定读取哪个 prompt 文件。
    #
    # 处理：
    # - 读取 prompt 文件。
    # - 让 mock model 根据 prompt 决定是否调用工具。
    # - 如果需要工具，就执行工具并记录 steps。
    #
    # 输出：
    # - 返回 answer、steps、prompt_snapshot，方便对比不同 prompt 的行为。
    prompt = load_prompt(prompt_version)
    model_decision = decide_actions(prompt=prompt, case=case)
    steps: list[dict[str, Any]] = [
        {
            "phase": "model_decision",
            "prompt_version": prompt["version"],
            "prompt_behavior": prompt["behavior"],
            "decision_type": model_decision["decision_type"],
            "reason": model_decision["reason"],
        }
    ]
    step_outputs: dict[str, dict[str, Any]] = {}

    if model_decision["decision_type"] == "final_answer":
        return {
            "status": "succeeded",
            "answer": model_decision["answer"],
            "tool_call_count": 0,
            "steps": steps,
            "prompt_snapshot": {
                "version": prompt["version"],
                "behavior": prompt["behavior"],
                "path": prompt["path"],
            },
        }

    for index, tool_call in enumerate(model_decision["tool_calls"], start=1):
        try:
            arguments = resolve_arguments(
                raw_arguments=tool_call["arguments"],
                step_outputs=step_outputs,
            )
        except KeyError as exc:
            steps.append(
                {
                    "phase": "tool_call",
                    "step_number": index,
                    "step_id": tool_call["step_id"],
                    "tool_name": tool_call["tool_name"],
                    "status": "failed",
                    "error": f"参数引用失败：{exc}",
                    "why": tool_call["why"],
                }
            )
            return {
                "status": "failed",
                "answer": "工具参数引用失败，请检查 prompt 生成的工具调用参数。",
                "tool_call_count": index,
                "steps": steps,
                "prompt_snapshot": {
                    "version": prompt["version"],
                    "behavior": prompt["behavior"],
                    "path": prompt["path"],
                },
            }

        started_at = datetime.now()
        tool_result = run_tool(tool_name=tool_call["tool_name"], arguments=arguments)
        ended_at = datetime.now()
        duration_ms = round((ended_at - started_at).total_seconds() * 1000, 3)

        if not tool_result["ok"]:
            steps.append(
                {
                    "phase": "tool_call",
                    "step_number": index,
                    "step_id": tool_call["step_id"],
                    "tool_name": tool_call["tool_name"],
                    "status": "failed",
                    "arguments": arguments,
                    "error": tool_result["error"],
                    "duration_ms": duration_ms,
                    "why": tool_call["why"],
                }
            )
            return {
                "status": "failed",
                "answer": "工具执行失败，请查看 steps 中的 error 字段。",
                "tool_call_count": index,
                "steps": steps,
                "prompt_snapshot": {
                    "version": prompt["version"],
                    "behavior": prompt["behavior"],
                    "path": prompt["path"],
                },
            }

        step_outputs[tool_call["step_id"]] = tool_result["data"]
        steps.append(
            {
                "phase": "tool_call",
                "step_number": index,
                "step_id": tool_call["step_id"],
                "tool_name": tool_call["tool_name"],
                "status": "succeeded",
                "arguments": arguments,
                "output": tool_result["data"],
                "duration_ms": duration_ms,
                "why": tool_call["why"],
            }
        )

    refund_result = step_outputs.get("refund")
    if not refund_result:
        return {
            "status": "failed",
            "answer": "模型计划没有生成退款计算结果。",
            "tool_call_count": len(model_decision["tool_calls"]),
            "steps": steps,
            "prompt_snapshot": {
                "version": prompt["version"],
                "behavior": prompt["behavior"],
                "path": prompt["path"],
            },
        }

    if refund_result["eligible"]:
        answer = (
            f"根据 prompt {prompt_version} 的工具优先策略，系统已先查询制度再计算金额。"
            f"本单预计可退款 {refund_result['refund_amount']} 元。原因：{refund_result['reason']}"
        )
    else:
        answer = (
            f"根据 prompt {prompt_version} 的工具优先策略，系统已先查询制度再判断。"
            f"本单暂不符合自动退款条件。原因：{refund_result['reason']}"
        )

    return {
        "status": "succeeded",
        "answer": answer,
        "tool_call_count": len(model_decision["tool_calls"]),
        "steps": steps,
        "prompt_snapshot": {
            "version": prompt["version"],
            "behavior": prompt["behavior"],
            "path": prompt["path"],
        },
    }

from datetime import datetime
from typing import Any

from planner import build_plan
from tools import run_tool


def resolve_argument_value(value: Any, step_outputs: dict[str, dict[str, Any]]) -> Any:
    # 多工具编排的核心难点之一：后一个工具的参数可能来自前一个工具的输出。
    #
    # 如果 value 是 {"from_step": "policy", "field": "policy"}，
    # 它表示：去 policy 这一步的输出里取 policy 字段。
    #
    # Java 类比：这有点像工作流引擎里的变量引用，例如 ${policy.policy}。
    if isinstance(value, dict) and "from_step" in value and "field" in value:
        source_step_id = value["from_step"]
        field_name = value["field"]
        return step_outputs[source_step_id][field_name]

    if isinstance(value, dict):
        # 普通 dict 需要递归处理，因为里面可能还有 from_step 引用。
        return {
            key: resolve_argument_value(inner_value, step_outputs)
            for key, inner_value in value.items()
        }

    if isinstance(value, list):
        # 列表里的每一项也可能引用前面步骤的输出。
        return [resolve_argument_value(item, step_outputs) for item in value]

    # 字符串、数字、布尔值这类普通值直接返回。
    return value


def resolve_arguments(
    raw_arguments: dict[str, Any],
    step_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    # raw_arguments 是 planner 生成的原始参数。
    # resolve 后，工具拿到的就是普通 Python dict，不需要理解 from_step 这种工作流语法。
    return {
        name: resolve_argument_value(value, step_outputs)
        for name, value in raw_arguments.items()
    }


def has_failed_dependency(
    depends_on: list[str],
    step_status_by_id: dict[str, str],
) -> str | None:
    # 如果当前步骤依赖的前置步骤失败了，当前步骤就不能继续执行。
    # 例如 policy 失败后，refund 就拿不到退款制度，继续算只会得到更隐蔽的错误。
    for dependency_step_id in depends_on:
        if step_status_by_id.get(dependency_step_id) != "succeeded":
            return dependency_step_id
    return None


def run_orchestration(case: dict[str, Any]) -> dict[str, Any]:
    # 这是本模块的核心函数：多工具编排。
    #
    # 单工具调用只关心“一次动作”。
    # 最小 Agent Loop 关心“模型是否要继续下一轮”。
    # 多工具编排关心“多个工具之间的顺序、依赖、数据传递和错误影响范围”。
    #
    # Java 类比：可以把它理解成一个 Workflow Orchestrator。
    plan = build_plan(case)
    steps: list[dict[str, Any]] = []
    step_outputs: dict[str, dict[str, Any]] = {}
    step_status_by_id: dict[str, str] = {}

    for step_number, planned_step in enumerate(plan["steps"], start=1):
        step_id = planned_step["step_id"]
        tool_name = planned_step["tool_name"]
        depends_on = planned_step["depends_on"]

        failed_dependency = has_failed_dependency(depends_on, step_status_by_id)
        if failed_dependency:
            # 依赖失败时，不执行当前工具，而是记录 skipped。
            # 这比让工具拿着空参数继续跑更容易排查问题。
            step_status_by_id[step_id] = "skipped"
            steps.append(
                {
                    "step_number": step_number,
                    "step_id": step_id,
                    "tool_name": tool_name,
                    "status": "skipped",
                    "depends_on": depends_on,
                    "error": f"依赖步骤 {failed_dependency} 没有成功，当前步骤被跳过。",
                    "duration_ms": 0,
                    "planned_reason": planned_step["why"],
                }
            )
            continue

        try:
            arguments = resolve_arguments(
                raw_arguments=planned_step["arguments"],
                step_outputs=step_outputs,
            )
        except KeyError as exc:
            # 这里通常说明 planner 写错了 from_step 或 field。
            # 对初学者来说，这是很典型的多工具数据流错误。
            step_status_by_id[step_id] = "failed"
            steps.append(
                {
                    "step_number": step_number,
                    "step_id": step_id,
                    "tool_name": tool_name,
                    "status": "failed",
                    "depends_on": depends_on,
                    "error": f"参数引用失败，找不到前置输出：{exc}",
                    "duration_ms": 0,
                    "planned_reason": planned_step["why"],
                }
            )
            if case["stop_on_error"]:
                break
            continue

        started_at = datetime.now()
        tool_result = run_tool(tool_name=tool_name, arguments=arguments)
        ended_at = datetime.now()
        duration_ms = round((ended_at - started_at).total_seconds() * 1000, 3)

        if tool_result["ok"]:
            step_status_by_id[step_id] = "succeeded"
            step_outputs[step_id] = tool_result["data"]
            steps.append(
                {
                    "step_number": step_number,
                    "step_id": step_id,
                    "tool_name": tool_name,
                    "status": "succeeded",
                    "arguments": arguments,
                    "output": tool_result["data"],
                    "depends_on": depends_on,
                    "duration_ms": duration_ms,
                    "parallel_group": planned_step["parallel_group"],
                    "planned_reason": planned_step["why"],
                }
            )
            continue

        step_status_by_id[step_id] = "failed"
        steps.append(
            {
                "step_number": step_number,
                "step_id": step_id,
                "tool_name": tool_name,
                "status": "failed",
                "arguments": arguments,
                "error": tool_result["error"],
                "depends_on": depends_on,
                "duration_ms": duration_ms,
                "parallel_group": planned_step["parallel_group"],
                "planned_reason": planned_step["why"],
            }
        )
        if case["stop_on_error"]:
            break

    final_reply = step_outputs.get("reply", {}).get("reply")
    failed_steps = [
        step for step in steps if step["status"] in {"failed", "skipped"}
    ]

    if final_reply:
        status = "succeeded"
        answer = final_reply
    else:
        status = "failed"
        answer = "Agent 没有生成最终客服回复。请查看 steps，通常是前置工具失败或依赖步骤被跳过。"

    return {
        "status": status,
        "answer": answer,
        "plan": plan,
        "summary": {
            "total_steps": len(steps),
            "succeeded_steps": len(
                [step for step in steps if step["status"] == "succeeded"]
            ),
            "failed_or_skipped_steps": len(failed_steps),
            "stop_on_error": case["stop_on_error"],
        },
        "steps": steps,
    }

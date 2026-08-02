from datetime import datetime
from typing import Any

from provider import decide_next_action
from tools import run_tool


def run_agent(
    user_message: str,
    system_prompt: str,
    max_steps: int,
    allow_tools: bool,
) -> dict[str, Any]:
    # 这是本模块的核心函数：最小 Agent Loop。
    #
    # 普通工具调用模块只执行一次：
    # 用户问题 -> 模型决定 -> 工具执行 -> 最终回答
    #
    # Agent Loop 会多一层循环：
    # 用户目标 -> 模型决定 -> 工具执行 -> observation -> 再让模型决定下一步
    #
    # Java 类比：可以把这个函数理解成一个 Orchestrator，负责协调“模型决策”和“工具执行”。
    steps: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    # range(1, max_steps + 1) 会生成 1 到 max_steps。
    # 这里不用 while True，是因为教学阶段要明确看到“最大步数”如何防止无限循环。
    for step_number in range(1, max_steps + 1):
        decision = decide_next_action(
            user_message=user_message,
            system_prompt=system_prompt,
            observations=observations,
            allow_tools=allow_tools,
        )
        steps.append(
            {
                "step_number": step_number,
                "phase": "model_decision",
                "decision": decision,
            }
        )

        if decision["type"] == "final_answer":
            # final_answer 表示模型认为已经可以停止。
            # 这里立刻 return，后面的工具执行不会发生。
            return {
                "status": "succeeded",
                "stopped_by": "final_answer",
                "answer": decision["answer"],
                "step_count": step_number,
                "steps": steps,
            }

        if decision["type"] == "tool_call":
            # 模型不会真的执行工具。
            # 它只给出 tool_name 和 arguments，后端再通过 run_tool 白名单执行。
            time_start = datetime.now()
            tool_output = run_tool(
                tool_name=decision["tool_name"],
                arguments=decision["arguments"],
            )
            time_end = datetime.now()
            observation = {
                "tool_name": decision["tool_name"],
                "arguments": decision["arguments"],
                "output": tool_output,
                "execution_time": (time_end - time_start).total_seconds(),
            }
            observations.append(observation)
            steps.append(
                {
                    "step_number": step_number,
                    "phase": "observation",
                    "observation": observation,
                }
            )
            continue

        # 如果 provider 返回了未知类型，说明“模型决策契约”被破坏。
        # 后端应该给出清晰错误，而不是继续执行不可预期逻辑。
        return {
            "status": "failed",
            "stopped_by": "invalid_decision",
            "answer": f"模型返回了未知决策类型：{decision.get('type')}",
            "step_count": step_number,
            "steps": steps,
        }

    # 走到这里，说明每一轮都选择了继续调用工具，但没有生成最终回答。
    # 这正是 max_steps 要解决的问题：防止 Agent 无限循环、耗尽费用或拖垮服务。
    return {
        "status": "stopped",
        "stopped_by": "max_steps",
        "answer": f"Agent 已达到最大步数 {max_steps}，为了防止无限循环，后端主动停止执行。",
        "step_count": max_steps,
        "steps": steps,
    }

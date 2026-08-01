from typing import Any

from tools import create_todo, make_learning_plan, search_agent_notes


# agent.py 负责“最小 Agent 流程”。
# Java 类比：它类似一个 Application Service，负责把多个业务动作串成一条完整流程。
# 注意：这个模块故意不用真实大模型，先用规则模拟“思考和选择动作”。


def basic_chat_reply(message: str) -> dict[str, Any]:
    # 普通聊天接口只根据输入生成回答。
    # 它不会主动查资料、拆计划、创建任务，也不会记录中间步骤。
    return {
        "reply": (
            f"你问的是：{message}。"
            "普通聊天会直接生成一句回答，但不会主动执行额外动作。"
        ),
        "mode": "basic_chat",
    }


def decide_action(goal: str, allow_action: bool) -> dict[str, Any]:
    # decide_action 是教学版“思考步骤”。
    # 真实 Agent 通常会让模型做这个判断；这里用 if 规则，让初学者先看懂分支流程。
    if not allow_action:
        return {
            "action": "direct_answer",
            "reason": "allow_action=false，本次请求禁止 Agent 执行动作。",
            "arguments": {},
        }

    if "计划" in goal or "学习" in goal or "怎么学" in goal:
        return {
            "action": "make_learning_plan",
            "reason": "用户目标是学习或计划，适合先拆成可执行步骤。",
            "arguments": {"topic": goal},
        }

    if "任务" in goal or "待办" in goal or "提醒" in goal:
        return {
            "action": "create_todo",
            "reason": "用户目标像是在创建一个待办事项，适合执行创建动作。",
            "arguments": {"goal": goal},
        }

    if "agent" in goal.lower() or "工具" in goal or "循环" in goal:
        keyword = "agent"
        if "工具" in goal:
            keyword = "工具"
        if "循环" in goal:
            keyword = "循环"

        return {
            "action": "search_agent_notes",
            "reason": "用户在问 Agent 相关概念，适合先查教学资料。",
            "arguments": {"keyword": keyword},
        }

    return {
        "action": "direct_answer",
        "reason": "这个目标不需要额外动作，直接回答即可。",
        "arguments": {},
    }


def run_action(decision: dict[str, Any]) -> dict[str, Any]:
    # run_action 根据 decision 里的 action 执行具体函数。
    # 这里是白名单分发：只有明确写在 if 里的动作才能执行。
    # 这点很重要，不能让 Agent 随便运行任意 Python 函数。
    action = decision["action"]
    arguments = decision["arguments"]

    if action == "make_learning_plan":
        return {
            "ok": True,
            "action": action,
            "observation": make_learning_plan(topic=arguments["topic"]),
        }

    if action == "create_todo":
        return {
            "ok": True,
            "action": action,
            "observation": create_todo(goal=arguments["goal"]),
        }

    if action == "search_agent_notes":
        return {
            "ok": True,
            "action": action,
            "observation": search_agent_notes(keyword=arguments["keyword"]),
        }

    return {
        "ok": True,
        "action": "direct_answer",
        "observation": {
            "message": "没有执行外部动作。",
        },
    }


def build_final_answer(goal: str, decision: dict[str, Any], action_result: dict[str, Any]) -> str:
    # final answer 是给用户看的最终回答。
    # Agent 的回答通常不只是“模型脑补的一句话”，而是结合了动作执行后的 observation。
    action = decision["action"]
    observation = action_result["observation"]

    if action == "make_learning_plan":
        plan_text = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(observation["plan"]))
        return f"我把目标拆成了一个最小学习计划：\n{plan_text}"

    if action == "create_todo":
        return (
            f"我已经创建了一个教学版待办：{observation['title']}。"
            f"任务编号：{observation['todo_id']}，下一步：{observation['next_action']}"
        )

    if action == "search_agent_notes":
        if not observation["found"]:
            return f"我没有在教学资料里查到和 {observation['keyword']} 相关的内容。"

        first_match = observation["matches"][0]
        return f"我先查了资料，再回答：{first_match['content']} 来源：{first_match['source']}。"

    return (
        f"对于“{goal}”，我判断不需要额外动作。"
        "这就是普通聊天和 Agent 的一个边界：不是所有问题都需要 Agent。"
    )


def run_minimal_agent(goal: str, allow_action: bool, max_steps: int) -> dict[str, Any]:
    # 这是本模块最核心的函数。
    # 它演示 Agent 的最小结构：
    # 1. 接收目标；
    # 2. 思考下一步；
    # 3. 执行动作；
    # 4. 观察结果；
    # 5. 生成最终回答。
    #
    # max_steps 在这里只做概念展示。
    # 后续 Agent Loop 模块会真正使用 max_steps 防止无限循环。
    steps: list[dict[str, Any]] = [
        {
            "step": "goal",
            "content": goal,
        }
    ]

    if max_steps < 1:
        return {
            "reply": "max_steps 必须至少为 1，否则 Agent 没有机会执行任何步骤。",
            "is_agent": True,
            "steps": steps,
        }

    decision = decide_action(goal=goal, allow_action=allow_action)
    steps.append(
        {
            "step": "think",
            "decision": decision,
        }
    )

    action_result = run_action(decision)
    steps.append(
        {
            "step": "act_and_observe",
            "result": action_result,
        }
    )

    reply = build_final_answer(goal=goal, decision=decision, action_result=action_result)
    steps.append(
        {
            "step": "final_answer",
            "content": reply,
        }
    )

    return {
        "reply": reply,
        "is_agent": True,
        "used_action": decision["action"] != "direct_answer",
        "action": decision["action"],
        "steps": steps,
    }

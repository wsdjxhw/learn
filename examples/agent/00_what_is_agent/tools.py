from typing import Any


# 这个文件里的函数先叫“动作函数”，不急着引入 tool schema。
# 后面的 01_tool_calling 模块才会正式学习“把工具描述给模型看”的 schema。
#
# Java 类比：这些函数有点像 Service 里的普通业务方法。
# Agent 会根据用户目标选择调用哪个方法，但真正执行动作的仍然是后端代码。


def search_agent_notes(keyword: str) -> dict[str, Any]:
    # 这是一个教学版资料检索函数。
    # 它不连接数据库，也不做向量检索，只用固定资料帮助初学者先理解 Agent 流程。
    notes = {
        "agent": (
            "Agent 可以理解成一个会围绕目标做事的程序。"
            "它不只是生成一句回答，还会决定下一步动作、执行动作、观察结果，再组织最终答复。"
        ),
        "工具": (
            "工具是后端暴露给 Agent 使用的能力，例如查询资料、计算金额、写入数据库、创建后台任务。"
        ),
        "循环": (
            "Agent Loop 是 Agent 的核心流程：思考下一步、执行动作、观察结果、判断是否结束。"
        ),
    }

    matched = []
    for note_keyword, content in notes.items():
        # 这里用最简单的关键词包含匹配。
        # 后续 RAG Agent 会把这种固定资料升级成真正的文档检索。
        if keyword in note_keyword or note_keyword in keyword:
            matched.append(
                {
                    "keyword": note_keyword,
                    "content": content,
                    "source": f"agent_note:{note_keyword}",
                }
            )

    if not matched:
        return {
            "found": False,
            "keyword": keyword,
            "matches": [],
        }

    return {
        "found": True,
        "keyword": keyword,
        "matches": matched,
    }


def make_learning_plan(topic: str) -> dict[str, Any]:
    # 这个函数模拟 Agent 为一个学习目标拆步骤。
    # 普通聊天可能只说“你应该学习 Agent”，而 Agent 更像是在完成一个目标：
    # 它会把目标拆成可执行步骤。
    return {
        "topic": topic,
        "plan": [
            f"先用一句话说清楚 {topic} 是什么。",
            f"再找出 {topic} 和已经学过内容的关系。",
            f"运行一个最小 {topic} 示例，观察输入、动作、输出。",
            f"最后修改一个小功能，确认自己真的能改动 {topic} 流程。",
        ],
    }


def create_todo(goal: str) -> dict[str, Any]:
    # 这个函数模拟“写入待办任务”。
    # 当前模块不接数据库，所以只是返回一个稳定的假任务。
    # 后续数据库工具 Agent 会学习真正的查询和写入。
    return {
        "todo_id": "todo-demo-001",
        "title": goal,
        "status": "created",
        "next_action": "打开 README，按接口测试顺序运行示例。",
    }

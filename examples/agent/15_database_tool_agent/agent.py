"""
agent.py —— Agent 循环：把"用户问题"变成"工具调用 + 回答"

这里是整个模块的入口业务逻辑，也是你 30 分钟应该先读懂的文件。

完整链路（初学者按这个顺序理解）：
  用户问题
    -> 模型 decide_tool：要不要调工具？调哪个？参数是什么？（可能返回 None = 直接回答）
    -> execute_tool：工具注册表的执行中枢（权限 -> 校验 -> 确认门 -> 执行 -> 审计）
    -> 得到 ToolResult，转成 observation
    -> 模型 compose_answer：根据 observation 生成最终自然语言回答

关于循环和 max_agent_steps：
  这里用一个 for 循环 + 最大步数上限，是因为真实 Agent 是"思考-行动-观察"
  反复进行的（模块 02 学过）。本模块聚焦数据库工具链路，通常一轮就完成
  （查询成功 / 等待确认后停下），但保留循环结构和上限，防止"失败后无限重试"。
"""

from provider import format_observation
from schemas import ChatResponse, StepOut
from security import UserContext
from settings import settings
from tool_registry import execute_tool, visible_tools_for_role


def run_agent(question: str, user: UserContext, provider) -> ChatResponse:
    """执行一次 Agent 对话，返回结构化结果（含中间 steps）。

    参数说明：
      question  用户的问题（来自请求体 ChatRequest.question）
      user      当前身份（来自请求头 X-API-Key，由 security.get_current_user 注入）
      provider  模型提供方（mock 或 DeepSeek，由 get_provider() 创建）
    """
    # 该角色能看到的工具白名单（viewer 看不到写工具和 SQL 工具）
    visible_tools = visible_tools_for_role(user.role)

    steps: list[StepOut] = []     # 记录每一步，最终返回给前端展示
    last_result = None            # 最后一次工具执行结果
    confirmation_id = None        # 如果触发写操作，保存确认单 id
    feedback = None               # 上一轮工具结果，用于失败后让模型纠错

    for _ in range(settings.max_agent_steps):
        # 第一步：让模型决定要不要调工具
        decision = provider.decide_tool(question, user.role, visible_tools, feedback)
        if decision is None:
            break  # 模型认为不需要工具，直接进入回答环节

        # 第二步：记录这次工具调用
        steps.append(StepOut(
            step="tool_call",
            tool_name=decision.tool_name,
            args=decision.args,
        ))

        # 第三步：执行工具（权限/校验/确认门/审计都在 execute_tool 内部完成）
        result = execute_tool(decision.tool_name, decision.args, user.role, user.api_key)

        # 第四步：记录观察结果（observation）
        steps.append(StepOut(step="observation", content=format_observation(result)))

        last_result = result
        confirmation_id = result.confirmation_id
        feedback = result

        # 查询成功 / 写操作已等待确认：都可以停下来了
        if result.status in ("awaiting_confirmation", "success"):
            break
        # failed / blocked：带着反馈再让模型决策一次（受 max_agent_steps 限制，
        # 防止模型反复调用同一个失败工具陷入死循环）

    # 最后一步：根据工具结果生成最终回答
    answer = provider.compose_answer(question, last_result, user.role)

    return ChatResponse(
        question=question,
        answer=answer,
        steps=steps,
        role=user.role,
        confirmation_id=confirmation_id,
    )

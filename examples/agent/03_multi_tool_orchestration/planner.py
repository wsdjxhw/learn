from typing import Any


def build_plan(case: dict[str, Any]) -> dict[str, Any]:
    # planner.py 是教学版“计划生成器”。
    #
    # 在真实 Agent 里，这一步通常由大模型根据用户目标决定：
    # 先调用哪个工具、后调用哪个工具、工具参数是什么。
    #
    # 本模块暂时不用真实模型，是为了让初学者稳定看懂“多工具编排”本身。
    # Java 类比：这里像一个非常简单的 Workflow Builder，先生成工作流定义，再交给执行器跑。
    return {
        "goal": case["goal"],
        "plan_notes": [
            "policy 和 risk 两步都只依赖请求体，所以理论上可以并行。",
            "refund 需要同时拿到 policy 和 risk 的输出，所以必须等前两步完成。",
            "reply 需要退款计算结果，所以必须放在最后。",
        ],
        "steps": [
            {
                "step_id": "policy",
                "tool_name": "search_refund_policy",
                "arguments": {
                    "keyword": case["policy_keyword"],
                },
                "depends_on": [],
                "parallel_group": "prepare",
                "why": "先查制度，后面的计算才能知道退款窗口和退款比例。",
            },
            {
                "step_id": "risk",
                "tool_name": "evaluate_order_risk",
                "arguments": {
                    "days_since_purchase": case["days_since_purchase"],
                    "item_problem": case["item_problem"],
                },
                "depends_on": [],
                "parallel_group": "prepare",
                "why": "先判断订单风险，后面的计算要用这个结果决定是否优先处理。",
            },
            {
                "step_id": "vip",
                "tool_name": "check_vip_customer",
                "arguments": {
                    "customer_id": case["customer_id"],
                },
                "depends_on": [],
                "parallel_group": "prepare",
                "why": "检查客户是否为 VIP 客户，这个结果可能会影响后续的处理策略。",
            },
            {
                "step_id": "refund",
                "tool_name": "calculate_refund",
                "arguments": {
                    "order_amount": case["order_amount"],
                    "days_since_purchase": case["days_since_purchase"],
                    "item_problem": case["item_problem"],
                    # from_step 表示这个参数不是来自用户请求，而是来自前面某个工具的输出。
                    # 这就是多工具编排里最重要的数据传递。
                    "policy": {"from_step": "policy", "field": "policy"},
                    "risk_flags": {"from_step": "risk", "field": "risk_flags"},
                    "is_vip": {"from_step": "vip", "field": "is_vip"},
                },
                "depends_on": ["policy", "risk", "vip"],
                "parallel_group": "calculate",
                "why": "退款金额依赖制度和订单风险，所以不能提前执行。",
            },
            {
                "step_id": "reply",
                "tool_name": "draft_customer_reply",
                "arguments": {
                    "customer_name": case["customer_name"],
                    "refund_result": {"from_step": "refund", "field": "refund_result"},
                    "policy_summary": {"from_step": "policy", "field": "summary"},
                },
                "depends_on": ["refund", "policy"],
                "parallel_group": "final",
                "why": "最终回复要引用计算结果和制度摘要，必须最后生成。",
            },
        ],
    }

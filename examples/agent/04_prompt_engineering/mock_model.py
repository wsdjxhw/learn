from typing import Any


def decide_actions(prompt: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    # 这是教学版 mock model。
    #
    # 真实模型会读 system prompt 和用户问题，然后生成回答或工具调用。
    # 本模块为了稳定演示 prompt 版本差异，用 prompt 文件里的 PROMPT_BEHAVIOR 标签控制行为。
    #
    # Java 类比：可以把它理解成一个可预测的 FakeModel，专门用于本地测试 prompt 改动。
    behavior = prompt["behavior"]
    user_message = case["message"]

    if "退款" not in user_message and "退货" not in user_message:
        return {
            "decision_type": "final_answer",
            "reason": "用户问题不是退款相关，不需要调用退款工具。",
            "answer": "这个示例只演示退款场景。请尝试提问：帮客户判断退款金额。",
            "tool_calls": [],
        }

    if behavior == "DIRECT_ANSWER":
        # v1 的问题：没有强制查制度和计算工具，容易直接给出模糊回答。
        return {
            "decision_type": "final_answer",
            "reason": "当前 prompt 倾向直接回答，没有要求先使用工具核算金额。",
            "answer": "可以先安抚客户，并建议客户提交退款申请。具体金额需要人工进一步确认。",
            "tool_calls": [],
        }

    if behavior == "TOOL_FIRST":
        # v2 的改进：涉及退款金额时，必须先查制度，再计算。
        return {
            "decision_type": "tool_plan",
            "reason": "当前 prompt 要求退款金额必须由工具计算，不能靠自然语言猜测。",
            "tool_calls": [
                {
                    "step_id": "policy",
                    "tool_name": "search_refund_policy",
                    "arguments": {"keyword": "退款"},
                    "why": "先查制度，避免直接编造退款窗口和比例。",
                },
                {
                    "step_id": "refund",
                    "tool_name": "calculate_refund",
                    "arguments": {
                        "order_amount": case["order_amount"],
                        "days_since_purchase": case["days_since_purchase"],
                        "item_problem": case["item_problem"],
                        "policy": {"from_step": "policy", "field": "policy"},
                    },
                    "why": "再用制度和订单信息计算退款金额。",
                },
            ],
        }

    return {
        "decision_type": "final_answer",
        "reason": f"未知 prompt 行为标签：{behavior}",
        "answer": "当前 prompt 没有可识别的行为策略，后端选择保守停止。",
        "tool_calls": [],
    }

from typing import Any


class ToolExecutionError(Exception):
    """工具执行失败时主动抛出的错误。"""


# 工具 schema 是“给 planner / 模型看的工具说明书”。
# Java 类比：它像接口文档，说明方法名、参数和能力；但真正执行仍然要走后端白名单。
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_refund_policy",
        "description": "检索教学版退款制度，返回退款窗口和退款比例。",
        "input": {"keyword": "制度关键词，例如：退款、退货。"},
    },
    {
        "name": "evaluate_order_risk",
        "description": "根据购买天数和商品问题判断订单处理风险。",
        "input": {
            "days_since_purchase": "购买后经过天数。",
            "item_problem": "商品问题，例如：破损、不喜欢、未收到、其他。",
        },
    },
    {
        "name": "calculate_refund",
        "description": "结合订单金额、退款制度和风险标记计算退款金额。",
        "input": {
            "order_amount": "订单金额。",
            "days_since_purchase": "购买后经过天数。",
            "item_problem": "商品问题。",
            "policy": "search_refund_policy 的输出。",
            "risk_flags": "evaluate_order_risk 的输出。",
        },
    },
    {
        "name": "check_vip_customer",
        "description": "检查客户是否为 VIP 客户。",
        "input": {"customer_id": "客户 ID。"},
    },
    {
        "name": "draft_customer_reply",
        "description": "根据退款计算结果生成客服回复草稿。",
        "input": {
            "customer_name": "客户姓名。",
            "refund_result": "calculate_refund 的输出。",
            "policy_summary": "search_refund_policy 的制度摘要。",
        },
    },
]


def list_tool_schemas() -> list[dict[str, Any]]:
    # 这个函数给 /tools 接口使用。
    # 返回一份列表，而不是直接暴露内部变量，是为了以后方便做过滤、权限控制或版本管理。
    return TOOL_SCHEMAS


def search_refund_policy(keyword: str) -> dict[str, Any]:
    # 这里模拟一个很小的制度库。
    # 后续 RAG 工具智能体模块会把它升级成真正的文档检索工具。
    policy_by_keyword = {
        "退款": {
            "name": "7 天退款制度",
            "return_window_days": 7,
            "damaged_refund_rate": 1.0,
            "normal_refund_rate": 0.8,
            "summary": "购买 7 天内可申请退款；商品破损可全额退款，非质量问题按 80% 退款。",
        },
        "退货": {
            "name": "7 天退货制度",
            "return_window_days": 7,
            "damaged_refund_rate": 1.0,
            "normal_refund_rate": 0.8,
            "summary": "购买 7 天内可退货；破损商品优先处理。",
        },
    }

    if keyword not in policy_by_keyword:
        # 主动抛出业务错误，而不是返回空字典。
        # 原因是后端需要明确知道“这个工具失败了”，后面依赖它的步骤不能继续假装成功。
        raise ToolExecutionError(f"没有找到关键词 {keyword} 对应的退款制度")

    policy = policy_by_keyword[keyword]
    return {
        "keyword": keyword,
        "policy": policy,
        "summary": policy["summary"],
    }


def evaluate_order_risk(days_since_purchase: int, item_problem: str) -> dict[str, Any]:
    # 这个工具不依赖制度检索结果，只依赖用户请求体。
    # 所以它和 search_refund_policy 属于同一个 prepare 阶段，理论上可以并行。
    risk_flags: list[str] = []

    if item_problem == "破损":
        risk_flags.append("quality_issue")
    if item_problem == "未收到":
        risk_flags.append("delivery_issue")
    if days_since_purchase > 7:
        risk_flags.append("outside_normal_window")

    priority = "high" if "quality_issue" in risk_flags or "delivery_issue" in risk_flags else "normal"
    return {
        "risk_flags": risk_flags,
        "priority": priority,
        "summary": f"订单优先级为 {priority}，风险标记：{risk_flags or ['none']}。",
    }

def check_vip_customer(customer_id: str) -> dict[str, Any]:
    # 这个工具不依赖制度检索结果，只依赖用户请求体。
    # 所以它和 search_refund_policy 属于同一个 prepare 阶段，理论上可以并行。
    vip_customers = {"CUST123", "CUST456", "CUST789"}
    is_vip = customer_id in vip_customers
    return {
        "customer_id": customer_id,
        "is_vip": is_vip,
        "summary": f"客户 {customer_id} {'是' if is_vip else '不是'} VIP 客户。",
    }

def calculate_refund(
    order_amount: float,
    days_since_purchase: int,
    item_problem: str,
    policy: dict[str, Any],
    risk_flags: list[str],
    is_vip: bool,
) -> dict[str, Any]:
    # 工具内部仍然必须校验参数。
    # 参数可能来自用户，也可能来自前面工具的输出；两者都不能默认可信。
    if order_amount <= 0:
        raise ToolExecutionError("order_amount 必须大于 0")

    return_window_days = int(policy["return_window_days"])
    if days_since_purchase > return_window_days and "quality_issue" not in risk_flags:
        return {
            "refund_result": {
                "eligible": False,
                "refund_amount": 0,
                "reason": f"已超过 {return_window_days} 天退款窗口，且不是质量问题。",
            }
        }

    if item_problem == "破损" or "quality_issue" in risk_flags:
        refund_rate = float(policy["damaged_refund_rate"])
        reason = "商品存在质量问题，按制度可全额退款。"
    else:
        refund_rate = float(policy["normal_refund_rate"])
        reason = "在退款窗口内，但不是质量问题，按普通比例退款。"

    if is_vip:
        # VIP 客户享受额外 5% 的退款比例加成。
        refund_rate = min(refund_rate + 0.05, 1.0)
        reason += " VIP 客户享受额外 5% 的退款比例加成。"

    refund_amount = round(order_amount * refund_rate, 2)
    return {
        "refund_result": {
            "eligible": True,
            "refund_amount": refund_amount,
            "refund_rate": refund_rate,
            "reason": reason,
        }
    }


def draft_customer_reply(
    customer_name: str,
    refund_result: dict[str, Any],
    policy_summary: str,
) -> dict[str, Any]:
    # 这个工具相当于“最后的自然语言组织层”。
    # 真实项目里可以让大模型生成措辞，但金额、资格、制度依据必须来自前面工具的结构化结果。
    if refund_result["eligible"]:
        reply = (
            f"{customer_name}，您好。根据当前订单信息，您的订单符合退款条件，"
            f"预计可退款 {refund_result['refund_amount']} 元。依据：{policy_summary}"
        )
    else:
        reply = (
            f"{customer_name}，您好。根据当前订单信息，本次暂不符合自动退款条件。"
            f"原因：{refund_result['reason']} 如您有补充凭证，可以继续提交人工审核。"
        )

    return {
        "reply": reply,
    }


def run_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # run_tool 是唯一的工具执行入口。
    # Java 类比：可以把它看成 ToolService.dispatch(name, args)。
    # 这样 orchestrator.py 不需要知道每个工具函数的细节，只需要传入工具名和参数。
    try:
        if tool_name == "search_refund_policy":
            data = search_refund_policy(keyword=str(arguments.get("keyword", "")))
        elif tool_name == "evaluate_order_risk":
            data = evaluate_order_risk(
                days_since_purchase=int(arguments.get("days_since_purchase", 0)),
                item_problem=str(arguments.get("item_problem", "")),
            )
        elif tool_name == "calculate_refund":
            data = calculate_refund(
                order_amount=float(arguments.get("order_amount", 0)),
                days_since_purchase=int(arguments.get("days_since_purchase", 0)),
                item_problem=str(arguments.get("item_problem", "")),
                policy=dict(arguments.get("policy", {})),
                risk_flags=list(arguments.get("risk_flags", [])),
                is_vip=bool(arguments.get("is_vip", False)),
            )
        elif tool_name == "draft_customer_reply":
            data = draft_customer_reply(
                customer_name=str(arguments.get("customer_name", "")),
                refund_result=dict(arguments.get("refund_result", {})),
                policy_summary=str(arguments.get("policy_summary", "")),
            )
        elif tool_name == "check_vip_customer":
            data = check_vip_customer(customer_id=str(arguments.get("customer_id", "")))
        else:
            raise ToolExecutionError(f"工具 {tool_name} 不在白名单中")
    except (KeyError, TypeError, ValueError) as exc:
        # 这些异常常见于“上一步工具输出结构不符合预期”或“模型传错参数类型”。
        return {
            "ok": False,
            "error": f"工具参数或数据结构错误：{exc}",
        }
    except ToolExecutionError as exc:
        return {
            "ok": False,
            "error": str(exc),
        }

    return {
        "ok": True,
        "data": data,
    }

from typing import Any


class ToolExecutionError(Exception):
    """工具执行失败时主动抛出的错误。"""


# 工具清单保留在代码里，prompt 负责“什么时候用工具”，工具代码负责“怎么安全执行”。
# Java 类比：prompt 像业务规则说明，tools.py 像真正的 Service 方法集合。
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_refund_policy",
        "description": "查询退款制度，适合判断退款窗口、退款比例和是否需要人工审核。",
        "input": {"keyword": "制度关键词，例如：退款。"},
    },
    {
        "name": "calculate_refund",
        "description": "根据订单金额、购买天数、商品问题和退款制度计算退款结果。",
        "input": {
            "order_amount": "订单金额。",
            "days_since_purchase": "购买后经过天数。",
            "item_problem": "商品问题。",
            "policy": "退款制度工具返回的 policy 字段。",
        },
    },
]


def list_tool_schemas() -> list[dict[str, Any]]:
    return TOOL_SCHEMAS


def search_refund_policy(keyword: str) -> dict[str, Any]:
    # 本模块重点是 prompt 工程，不是 RAG，所以制度数据仍然使用固定 mock。
    if keyword != "退款":
        raise ToolExecutionError(f"没有找到关键词 {keyword} 对应的制度")

    policy = {
        "return_window_days": 7,
        "damaged_refund_rate": 1.0,
        "normal_refund_rate": 0.8,
        "manual_review_after_days": 7,
    }
    return {
        "policy": policy,
        "summary": "购买 7 天内可申请退款；商品破损可全额退款，非质量问题按 80% 退款。",
    }


def calculate_refund(
    order_amount: float,
    days_since_purchase: int,
    item_problem: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    # 即使 prompt 要求模型先查工具，后端工具仍然要做参数校验。
    # prompt 不是安全边界，工具白名单和参数校验才是后端边界。
    if order_amount <= 0:
        raise ToolExecutionError("order_amount 必须大于 0")

    return_window_days = int(policy["return_window_days"])
    if days_since_purchase > return_window_days and item_problem != "破损":
        return {
            "eligible": False,
            "refund_amount": 0,
            "reason": f"超过 {return_window_days} 天退款窗口，建议转人工审核。",
        }

    if item_problem == "破损":
        refund_rate = float(policy["damaged_refund_rate"])
        reason = "商品破损，按制度可全额退款。"
    else:
        refund_rate = float(policy["normal_refund_rate"])
        reason = "在退款窗口内，按普通退款比例处理。"

    return {
        "eligible": True,
        "refund_amount": round(order_amount * refund_rate, 2),
        "refund_rate": refund_rate,
        "reason": reason,
    }


def run_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # run_tool 是唯一工具入口，避免 prompt 或模型绕过白名单调用任意函数。
    try:
        if tool_name == "search_refund_policy":
            data = search_refund_policy(keyword=str(arguments.get("keyword", "")))
        elif tool_name == "calculate_refund":
            data = calculate_refund(
                order_amount=float(arguments.get("order_amount", 0)),
                days_since_purchase=int(arguments.get("days_since_purchase", 0)),
                item_problem=str(arguments.get("item_problem", "")),
                policy=dict(arguments.get("policy", {})),
            )
        else:
            raise ToolExecutionError(f"工具 {tool_name} 不在白名单中")
    except (KeyError, TypeError, ValueError) as exc:
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

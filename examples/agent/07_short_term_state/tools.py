from typing import Any


def search_refund_policy(query: str) -> dict[str, Any]:
    # 这是教学版检索工具。
    # 真实项目里这里可能调用 RAG、数据库、搜索服务；本模块先返回稳定结果，方便学习状态保存。
    return {
        "source_id": "refund-policy-001",
        "title": "售后退款规则",
        "content": "商品签收 7 天内，如果存在破损或质量问题，可以申请全额退款或补发。",
        "matched_query": query,
    }


def calculate_refund_amount(order_amount: int, is_damaged: bool) -> dict[str, Any]:
    # 这个工具展示“工具输出会成为后续 step 的输入”。
    # 如果商品破损，教学版直接返回全额退款；否则返回 0。
    if is_damaged:
        refund_amount = order_amount
    else:
        refund_amount = 0

    return {
        "currency": "CNY",
        "order_amount": order_amount,
        "refund_amount": refund_amount,
        "reason": "检测到破损场景，符合 7 天内售后规则。",
    }

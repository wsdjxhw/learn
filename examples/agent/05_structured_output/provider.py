import json
from typing import Any

from schemas import RefundDecision
from settings import get_settings


def _valid_payload(case: dict[str, Any]) -> dict[str, Any]:
    # 这个函数生成一份符合 RefundDecision 的标准 JSON 数据。
    # mock 模型不是为了“假装聪明”，而是为了让学习者稳定复现不同输出质量。
    problem = str(case.get("item_problem", ""))
    days = int(case.get("days_since_purchase", 0))
    amount = float(case.get("order_amount", 0))

    risk_flags: list[str] = []
    if amount >= 1000:
        risk_flags.append("high_amount")
    if days > 7:
        risk_flags.append("over_policy_days")

    if "破损" in problem or "质量" in problem:
        decision_type = "tool_call"
        category = "refund"
        priority = "high" if amount >= 1000 else "medium"
        action = {
            "tool_name": "calculate_refund",
            "arguments": {
                "order_amount": amount,
                "days_since_purchase": days,
                "item_problem": problem,
            },
            "reason": "质量问题需要按售后规则计算可退金额。",
        }
        answer = "我会先根据售后规则核算退款金额，再给出可执行结论。"
    elif days > 7:
        decision_type = "manual_review"
        category = "refund"
        priority = "medium"
        action = {
            "tool_name": "manual_review",
            "arguments": {
                "order_amount": amount,
                "days_since_purchase": days,
                "item_problem": problem,
            },
            "reason": "超过自动售后窗口，需要人工确认是否有例外政策。",
        }
        answer = "该订单可能超过自动处理范围，我会转人工进一步审核。"
    else:
        decision_type = "final_answer"
        category = "other"
        priority = "low"
        action = None
        answer = "目前信息不足以判断退款金额，请补充订单问题和期望处理方式。"

    return {
        "decision_type": decision_type,
        "category": category,
        "priority": priority,
        "summary": f"用户反馈：{case.get('message', '')}",
        "missing_fields": [],
        "risk_flags": risk_flags,
        "confidence": 0.86,
        "customer_sentiment": case.get("customer_sentiment", "neutral"),
        "action": action,
        "user_visible_answer": answer,
    }


def generate_mock_text(case: dict[str, Any], previous_error: str | None = None) -> str:
    # previous_error 不为空，表示第一次输出没有通过解析或校验。
    # 教学版 mock 在重试时返回正确 JSON，用来演示“失败后把错误反馈给模型再试一次”。
    payload = _valid_payload(case)
    if previous_error:
        return json.dumps(payload, ensure_ascii=False)

    scenario = case.get("mock_scenario", "valid_json")

    if scenario == "json_with_extra_text":
        return "下面是结构化结果：\n" + json.dumps(payload, ensure_ascii=False) + "\n请按这个结果处理。"

    if scenario == "missing_field":
        # 删除必填字段，Pydantic 会报 missing。
        payload.pop("confidence")
        return json.dumps(payload, ensure_ascii=False)

    if scenario == "wrong_type":
        # missing_fields 在契约里必须是 list[str]，这里故意给字符串。
        payload["missing_fields"] = "无"
        return json.dumps(payload, ensure_ascii=False)

    if scenario == "invalid_enum":
        # priority 只允许 low / medium / high，urgent 会被拒绝。
        payload["priority"] = "urgent"
        return json.dumps(payload, ensure_ascii=False)

    if scenario == "invalid_sentiment":
        # customer_sentiment 只允许 angry / neutral / polite，very_angry 会被拒绝。
        payload["customer_sentiment"] = "very_angry"
        return json.dumps(payload, ensure_ascii=False)

    if scenario == "broken_json":
        # 这类输出看起来像 JSON，但少了右花括号，json.loads 无法解析。
        return '{"decision_type": "tool_call", "category": "refund", "priority": "medium"'

    return json.dumps(payload, ensure_ascii=False)


def _build_deepseek_messages(case: dict[str, Any], previous_error: str | None) -> list[dict[str, str]]:
    # 真实模型模式里，把 Pydantic 生成的 JSON Schema 发给模型。
    # 注意：Schema 是“约束说明”，最终仍然必须由后端 parser.py 做解析和校验。
    schema = RefundDecision.model_json_schema()
    system_prompt = (
        "你是客服售后 Agent 的结构化输出模块。"
        "你只能返回一个 JSON object，不要写 Markdown，不要写解释。"
        "JSON 必须符合下面的 schema：\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    user_prompt = (
        "请把用户请求转成结构化决策。\n"
        f"用户输入：{case.get('message')}\n"
        f"订单金额：{case.get('order_amount')}\n"
        f"购买后天数：{case.get('days_since_purchase')}\n"
        f"商品问题：{case.get('item_problem')}"
    )
    if previous_error:
        user_prompt += (
            "\n上一次输出没有通过后端校验，错误如下：\n"
            f"{previous_error}\n"
            "请只返回修正后的 JSON object。"
        )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_deepseek_text(case: dict[str, Any], previous_error: str | None = None) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    # requests 放在函数内导入。
    # 这样 mock 模式即使暂时没有安装 requests，也不会影响学习者先跑通主流程。
    import requests

    response = requests.post(
        f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.deepseek_model,
            "messages": _build_deepseek_messages(case, previous_error),
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def generate_model_text(case: dict[str, Any], previous_error: str | None = None) -> str:
    settings = get_settings()
    if settings.model_mode == "deepseek":
        return generate_deepseek_text(case=case, previous_error=previous_error)

    return generate_mock_text(case=case, previous_error=previous_error)

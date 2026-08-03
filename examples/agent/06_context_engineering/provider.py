from schemas import ContextBuildResult, ContextMessage
from settings import get_settings


def _to_chat_messages(context: ContextBuildResult) -> list[dict[str, str]]:
    # DeepSeek 使用 OpenAI 兼容协议，messages 是 list[dict]。
    # ContextMessage 里有 source_type、keep_reason 等教学字段，但模型 API 只认识 role 和 content。
    return [{"role": item.role, "content": item.content} for item in context.messages]


def generate_mock_answer(context: ContextBuildResult) -> str:
    # mock 模型故意很简单：它通过上下文里是否出现某些关键词来生成回答。
    # 这样你能稳定观察“上下文构造变化 -> 回答变化”，不用担心真实模型每次随机发挥。
    packed_context = "\n".join(item.content for item in context.messages)

    if "黑金会员升级规则" in packed_context:
        return (
            "我被低相关会员资料干扰了：这个问题本来是退款售后，但上下文混入会员升级规则，"
            "回答可能会偏向会员权益。生产项目应该过滤这类低相关 source。"
        )

    if "refund_amount" in packed_context:
        return "工具已经算出退款金额：240 CNY。根据 observation，可直接告知用户符合全额退款条件。"

    if "工具执行失败" in packed_context:
        return "退款工具没有成功执行。当前缺少签收时间，建议先补充签收时间，再判断是否仍在 7 天售后窗口内。"

    if "商品签收 7 天内" in packed_context and ("破损" in packed_context or "质量问题" in packed_context):
        return "根据售后退款规则，签收 7 天内的破损或质量问题可以优先走全额退款或补发流程。来源：refund-policy-001。"

    return "当前上下文不足以给出可靠结论。请补充购买天数、商品问题、订单金额或可引用的售后资料。"


def generate_deepseek_answer(context: ContextBuildResult) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    # requests 放在函数内部导入。
    # 这样 mock 模式先跑通时，即使网络或真实模型配置没准备好，也不会影响学习主线。
    import requests

    response = requests.post(
        f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.deepseek_model,
            "messages": _to_chat_messages(context),
            "temperature": 0,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def generate_model_answer(context: ContextBuildResult) -> str:
    settings = get_settings()
    if settings.model_mode == "deepseek":
        return generate_deepseek_answer(context)
    return generate_mock_answer(context)

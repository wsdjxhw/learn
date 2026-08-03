from openai import OpenAI

from settings import get_settings


def generate_final_answer(user_goal: str, policy: dict, refund: dict) -> str:
    # provider.py 是模型调用层。
    # Java 类比：可以理解成调用外部模型服务的 Service。
    settings = get_settings()
    if settings.model_mode == "deepseek":
        return _generate_deepseek_answer(user_goal, policy, refund)
    return _generate_mock_answer(policy, refund)


def _generate_mock_answer(policy: dict, refund: dict) -> str:
    # mock 模式保证无 key 也能完整跑通。
    # 它不是为了模拟模型智能，而是为了稳定展示“step 保存 -> 查询 -> 最终回答”的完整链路。
    return (
        f"根据 {policy['source_id']}，商品签收 7 天内破损可以申请退款。"
        f"本次订单金额 {refund['order_amount']} {refund['currency']}，"
        f"建议退款 {refund['refund_amount']} {refund['currency']}。"
    )


def _generate_deepseek_answer(user_goal: str, policy: dict, refund: dict) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    # OpenAI 客户端可以通过 base_url 调用 DeepSeek 的 OpenAI 兼容接口。
    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "你是售后 Agent。请只根据工具结果回答，并说明依据。",
            },
            {
                "role": "user",
                "content": (
                    f"用户目标：{user_goal}\n"
                    f"检索到的规则：{policy}\n"
                    f"退款计算结果：{refund}\n"
                    "请给出简洁、可执行的中文回复。"
                ),
            },
        ],
    )
    return response.choices[0].message.content or ""

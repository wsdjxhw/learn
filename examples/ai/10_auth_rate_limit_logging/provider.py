from openai import OpenAI

from config import get_deepseek_api_key, get_deepseek_model

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MOCK_INPUT_COST_PER_1K = 0.001
MOCK_OUTPUT_COST_PER_1K = 0.002


def get_provider_name() -> str:
    if get_deepseek_api_key():
        return "deepseek"
    return "mock"


def get_model_name() -> str:
    return get_deepseek_model()


def estimate_tokens(text: str) -> int:
    # 教学版 token 估算：大致按 4 个字符 1 个 token。
    # 真实模型会返回 usage 字段，生产项目应该优先使用服务商返回的真实 token 数。
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    # 这里使用固定教学单价，不代表任何真实服务商当前价格。
    # 目的只是学习“模型调用后要把成本记录下来”。
    input_cost = input_tokens / 1000 * MOCK_INPUT_COST_PER_1K
    output_cost = output_tokens / 1000 * MOCK_OUTPUT_COST_PER_1K
    return round(input_cost + output_cost, 6)


def build_result(reply: str, prompt: str) -> dict:
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(reply)
    return {
        "reply": reply,
        "provider": get_provider_name(),
        "model": get_model_name(),
        "prompt_chars": len(prompt),
        "reply_chars": len(reply),
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "estimated_cost_usd": estimate_cost_usd(input_tokens, output_tokens),
    }


def generate_mock_reply(user_message: str, system_prompt: str) -> dict:
    prompt = f"{system_prompt}\n\nuser: {user_message}"
    reply = (
        f"[mock reply] 已通过鉴权并记录日志。你的消息是：{user_message}。"
        "本模块重点是 API Key、限流、请求日志、错误日志和成本记录。"
    )
    return build_result(reply=reply, prompt=prompt)


def generate_deepseek_reply(user_message: str, system_prompt: str) -> dict:
    # DeepSeek 调用仍然放在 provider.py。
    # main.py 不直接接触 OpenAI SDK，这样接口层和外部服务调用层职责更清楚。
    client = OpenAI(
        api_key=get_deepseek_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        stream=False,
    )
    reply = response.choices[0].message.content or ""
    prompt = f"{system_prompt}\n\nuser: {user_message}"
    return build_result(reply=reply, prompt=prompt)


def generate_reply(user_message: str, system_prompt: str) -> dict:
    if get_provider_name() == "deepseek":
        return generate_deepseek_reply(user_message, system_prompt)
    return generate_mock_reply(user_message, system_prompt)

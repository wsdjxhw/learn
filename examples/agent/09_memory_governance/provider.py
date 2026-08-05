from openai import OpenAI

from context_builder import build_memory_context
from models import UserMemory
from settings import get_settings


def generate_agent_answer(user_message: str, memories: list[UserMemory]) -> str:
    # provider.py 是模型调用层。
    # Java 类比：可以理解成调用外部模型服务的 Service。
    settings = get_settings()
    if settings.model_mode == "deepseek":
        return _generate_deepseek_answer(user_message, memories)
    return _generate_mock_answer(user_message, memories)


def _generate_mock_answer(user_message: str, memories: list[UserMemory]) -> str:
    # mock 模式保证没有 API Key 也能跑完整治理链路。
    if not memories:
        return f"我已收到：{user_message}。本轮没有通过治理过滤的长期记忆可用。"

    memory_text = "；".join([f"{memory.key}={memory.value}" for memory in memories])
    return f"我会只使用 active 且未过期的长期记忆：{memory_text}。针对你的问题：{user_message}"


def _generate_deepseek_answer(user_message: str, memories: list[UserMemory]) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是教学用 Agent。只能使用用户本轮问题和经过治理过滤的长期记忆。"
                    "不能使用已删除、已过期或被拒绝保存的敏感信息。"
                ),
            },
            {
                "role": "user",
                "content": f"{build_memory_context(memories)}\n\n用户本轮问题：{user_message}\n请给出简洁中文回答。",
            },
        ],
    )
    return response.choices[0].message.content or ""

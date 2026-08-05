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
    # mock 模式不是为了模拟完整大模型能力，而是为了稳定展示记忆检索和复用链路。
    if not memories:
        return f"我已收到：{user_message}。本轮还没有可复用的长期记忆。"

    memory_text = "；".join([f"{memory.key}={memory.value}" for memory in memories])
    return f"我会结合这些长期记忆回答：{memory_text}。针对你的问题：{user_message}"


def _generate_deepseek_answer(user_message: str, memories: list[UserMemory]) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    memory_context = build_memory_context(memories)
    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是教学用 Agent。你可以使用长期记忆改善回答，"
                    "但不能编造没有出现在长期记忆或用户问题里的个人信息。"
                ),
            },
            {
                "role": "user",
                "content": f"{memory_context}\n\n用户本轮问题：{user_message}\n请给出简洁中文回答。",
            },
        ],
    )
    return response.choices[0].message.content or ""

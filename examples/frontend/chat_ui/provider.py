import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"
DEFAULT_MODEL = "deepseek-v4-flash"

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_deepseek_api_key() -> str | None:
    # DeepSeek key 是“调用外部模型服务”的密钥，不等于用户访问本 API 的 key。
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        return None
    return api_key


def get_deepseek_model() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def get_provider_name() -> str:
    # 没有真实 DeepSeek key 时走 mock，保证这个前端模块无 key 也能完整跑通。
    if get_deepseek_api_key():
        return "deepseek"
    return "mock"


def format_history(history: list[dict]) -> str:
    # 把最近消息整理成适合放进 prompt 的文本。
    # 真实模型调用时，这一步通常会变成 messages=[...] 的多轮对话格式。
    history_lines = []
    for message in history:
        history_lines.append(f"{message['role']}: {message['content']}")
    return "\n".join(history_lines)


def find_previous_user_message(history: list[dict], current_message: str) -> str | None:
    # history 里包含当前这条 user 消息。
    # 为了演示短期记忆，这里找“当前消息之前的上一条 user 消息”。
    previous_messages = [
        message["content"]
        for message in history
        if message["role"] == "user" and message["content"] != current_message
    ]
    if not previous_messages:
        return None
    return previous_messages[-1]


def generate_mock_reply(user_message: str, sources: list[dict], history: list[dict]) -> str:
    # provider.py 可以类比成 Java 里的 Service。
    # 本模块的重点是前端页面和接口协作，所以默认使用 mock 回复。
    source_titles = "、".join(source["title"] for source in sources)
    previous_user_message = find_previous_user_message(
        history=history,
        current_message=user_message,
    )
    memory_note = "这是本会话里我看到的第一条用户消息。"
    if previous_user_message:
        memory_note = f"我还记得你上一条用户消息是：{previous_user_message}"

    return (
        f"你刚才发送的是：{user_message}\n\n"
        f"短期记忆：{memory_note}\n"
        f"本次生成前读取了最近 {len(history)} 条历史消息。\n\n"
        "这个教学版前端会把用户消息保存到 messages 表，"
        "再创建后台任务，页面通过 task_id 轮询任务状态。\n\n"
        f"本次回答附带的 sources：{source_titles}。\n\n"
        f"历史上下文预览：\n{format_history(history)}"
    )


def build_sources_context(sources: list[dict]) -> str:
    # sources 不是 OpenAI/DeepSeek messages。
    # 它没有 role/content 字段，所以不能直接塞进 messages 列表。
    # 正确做法是把 sources 整理成一段 context 文本，再放进 system 或 user 内容里。
    if not sources:
        return "本次没有可用 sources。"

    context_parts = []
    for index, source in enumerate(sources, start=1):
        context_parts.append(
            f"[source {index}] title={source['title']}, score={source['score']}\n"
            f"{source['snippet']}"
        )
    return "\n\n".join(context_parts)


def build_deepseek_messages(user_message: str, sources: list[dict], history: list[dict]) -> list[dict]:
    # history 里已经包含当前这条 user 消息，因为 main.py 会先保存 user message，
    # worker.py 再读取最近消息。这里不能重复追加当前 user message。
    #
    # 这里只保留 role/content 两个字段，避免把数据库 id、created_at 等字段传给模型。
    safe_history = [
        {"role": message["role"], "content": message["content"]}
        for message in history
        if message["role"] in {"user", "assistant"}
    ]
    if not safe_history:
        safe_history = [{"role": "user", "content": user_message}]

    sources_context = build_sources_context(sources)
    return [
        {
            "role": "system",
            "content": (
                "你是一个帮助用户学习 AI 应用开发的助手。"
                "请优先结合 conversation history 回答，必要时参考 sources。"
                "如果 sources 不相关，可以说明没有足够资料支持。"
                f"\n\nsources:\n{sources_context}"
            ),
        },
        *safe_history,
    ]


def generate_deepseek_reply(user_message: str, sources: list[dict], history: list[dict]) -> str:
    # 这个函数演示了如何在 provider.py 里调用 DeepSeek API。
    # 注意：这里仍然是在后端调用 DeepSeek，不是浏览器前端直接调用。
    # 浏览器不应该拿到 DEEPSEEK_API_KEY。
    api_key = get_deepseek_api_key()
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")

    client = OpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=get_deepseek_model(),
        messages=build_deepseek_messages(
            user_message=user_message,
            sources=sources,
            history=history,
        ),
        stream=False,
    )

    return response.choices[0].message.content or ""


def generate_reply(user_message: str, sources: list[dict], history: list[dict]) -> str:
    # 统一入口：
    # - 有 DeepSeek key：调用真实 DeepSeek。
    # - 没有 key：走 mock，保证学习模块仍然能跑通。
    if get_provider_name() == "deepseek":
        return generate_deepseek_reply(
            user_message=user_message,
            sources=sources,
            history=history,
        )
    return generate_mock_reply(
        user_message=user_message,
        sources=sources,
        history=history,
    )

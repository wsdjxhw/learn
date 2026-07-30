import os
import time
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"

# provider.py 负责模型调用细节，可以类比成 Java 里的 Service。
# main.py 只关心“我要普通回复”或“我要流式回复”，不直接写 OpenAI SDK 细节。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
    # DeepSeek 的密钥从 .env 或系统环境变量 DEEPSEEK_API_KEY 读取。
    # 没有真实 key 时返回 None，后面会自动走 mock，保证学习时先能跑通。
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        return None
    return api_key


def get_model_name() -> str:
    # 模型名也放在 .env，避免把环境差异写死在代码里。
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def get_provider_name() -> str:
    if get_api_key():
        return "deepseek"
    return "mock"


def build_mock_reply(user_message: str, system_prompt: str) -> str:
    # mock 回复用固定规则生成，不调用真实模型。
    # 这里故意返回稍长一点，方便在流式接口里观察“一段一段返回”的效果。
    return (
        f"[mock reply] 收到你的消息：{user_message}。"
        f"普通接口会等整段内容生成完再一次性返回。"
        f"流式接口会把这段内容拆成多个小片段逐步返回。"
        f"system_prompt 长度：{len(system_prompt)}。"
    )


def generate_reply(user_message: str, system_prompt: str) -> str:
    # 普通非流式回复：函数返回时，整段答案已经生成完成。
    if get_provider_name() == "mock":
        return build_mock_reply(user_message, system_prompt)

    client = OpenAI(
        api_key=get_api_key(),
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
    return response.choices[0].message.content or ""


def stream_mock_reply(user_message: str, system_prompt: str) -> Iterator[str]:
    # mock 流式回复：把完整回复拆成小块，每次 yield 一块。
    # yield 是 Python 生成器语法，可以理解成“函数先返回一部分，下次再接着执行”。
    reply = build_mock_reply(user_message, system_prompt)
    chunk_size = 8

    for start in range(0, len(reply), chunk_size):
        time.sleep(0.12)
        yield reply[start : start + chunk_size]


def stream_deepseek_reply(user_message: str, system_prompt: str) -> Iterator[str]:
    # 真实流式调用：stream=True 后，SDK 返回的不是完整答案，而是一段一段的增量。
    client = OpenAI(
        api_key=get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )
    stream = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        stream=True,
    )

    for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            yield delta


def stream_reply(user_message: str, system_prompt: str) -> Iterator[str]:
    # 统一流式入口：main.py 不需要知道背后是 mock 还是 DeepSeek。
    if get_provider_name() == "mock":
        yield from stream_mock_reply(user_message, system_prompt)
        return

    yield from stream_deepseek_reply(user_message, system_prompt)

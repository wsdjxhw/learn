import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"

# 读取当前示例目录下的 .env。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
    # 占位 key 不算真实 key，否则会误走真实 DeepSeek 调用。
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        return None
    return api_key


def get_model_name() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def get_provider_name() -> str:
    if get_api_key():
        return "deepseek"
    return "mock"


def generate_mock_reply(messages: list[dict]) -> str:
    # messages 是历史消息列表，最后一条通常是用户刚刚发来的问题。
    last_user_message = ""
    for message in reversed(messages):
        if message["role"] == "user":
            last_user_message = message["content"]
            break

    return f"[mock reply] 我收到你的消息：{last_user_message}"


def generate_deepseek_reply(messages: list[dict]) -> str:
    # DeepSeek 兼容 OpenAI SDK 的 chat completions 格式。
    client = OpenAI(
        api_key=get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=messages,
        stream=False,
    )
    return response.choices[0].message.content or ""


def generate_reply(messages: list[dict]) -> str:
    # 对 main.py 暴露统一入口，隐藏 mock 和 DeepSeek 的差异。
    if get_provider_name() == "deepseek":
        return generate_deepseek_reply(messages)
    return generate_mock_reply(messages)

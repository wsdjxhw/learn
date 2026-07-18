import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"

# 读取 provider.py 同目录下的 .env 文件。
# 把配置加载放在 provider 层，避免 main.py 和 provider.py 看到的配置不一致。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
    # DeepSeek 的密钥从 .env 或系统环境变量 DEEPSEEK_API_KEY 读取。
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        return None
    return api_key


def get_model_name() -> str:
    # 如果 .env 里没有配置 DEEPSEEK_MODEL，就使用默认模型。
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def get_provider_name() -> str:
    # 没有 DeepSeek key 时使用 mock，方便先学习接口结构。
    if get_api_key():
        return "deepseek"
    return "mock"


def generate_mock_reply(user_message: str, system_prompt: str) -> str:
    # mock 回复不调用真实模型，只用来确认接口流程已经跑通。
    return (
        f"[mock reply] 收到你的消息：{user_message}。"
        f"system_prompt 长度：{len(system_prompt)}。"
    )


def generate_deepseek_reply(user_message: str, system_prompt: str) -> str:
    # DeepSeek 兼容 OpenAI SDK，但要指定 DeepSeek 的 base_url 和 key。
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


def generate_reply(user_message: str, system_prompt: str) -> str:
    # 统一入口：main.py 只调用这个函数，不关心背后是真实 DeepSeek 还是 mock。
    if get_provider_name() == "deepseek":
        return generate_deepseek_reply(user_message, system_prompt)
    return generate_mock_reply(user_message, system_prompt)

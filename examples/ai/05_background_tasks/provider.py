import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"

# 从本模块目录读取 .env。
# 没有真实 key 时使用 mock，保证学习后台任务不依赖外部服务。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
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


def summarize_with_mock(input_text: str) -> str:
    # mock 摘要不调用真实模型。
    # 它保留“输入 -> 处理 -> 输出”的形状，方便先学习任务状态流转。
    preview = input_text.strip().replace("\n", " ")[:80]
    return f"[mock summary] 文本长度 {len(input_text)}，开头内容：{preview}"


def summarize_with_deepseek(input_text: str) -> str:
    # DeepSeek 兼容 OpenAI SDK 的 chat completions 格式。
    # 这个函数只负责模型调用，任务状态更新交给 worker.py。
    client = OpenAI(
        api_key=get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {
                "role": "system",
                "content": "你是一个文本摘要助手，请用简洁中文总结用户输入。",
            },
            {"role": "user", "content": input_text},
        ],
        stream=False,
    )
    return response.choices[0].message.content or ""


def summarize_text(input_text: str) -> str:
    # 对 worker.py 暴露统一入口。
    # worker 不需要知道当前使用 mock 还是 DeepSeek。
    if get_provider_name() == "deepseek":
        return summarize_with_deepseek(input_text)
    return summarize_with_mock(input_text)

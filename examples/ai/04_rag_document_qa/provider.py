import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
    # 没有真实 key 时走 mock，保证学习时可以先跑通 RAG 流程。
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


def build_context(chunks: list[dict]) -> str:
    # 把检索到的 chunks 拼成一段上下文。
    # 模型回答时只能基于这段 context，而不是凭空猜。
    context_parts = []
    for index, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[source {index}] "
            f"document={chunk['document_title']}, "
            f"chunk_id={chunk['id']}\n"
            f"{chunk['content']}"
        )
    return "\n\n".join(context_parts)


def generate_mock_answer(question: str, chunks: list[dict]) -> str:
    # mock 答案只说明检索到了什么，不调用真实模型。
    if not chunks:
        return "[mock answer] 没有检索到相关资料。"

    titles = [chunk["document_title"] for chunk in chunks]
    return (
        f"[mock answer] 问题是：{question}。"
        f"检索到 {len(chunks)} 个相关片段，来源文档：{', '.join(titles)}。"
    )


def generate_deepseek_answer(question: str, chunks: list[dict]) -> str:
    # RAG 的关键：先检索 context，再把 context 和 question 一起交给模型。
    context = build_context(chunks)
    client = OpenAI(
        api_key=get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个基于资料回答问题的助手。"
                    "只能根据用户提供的 context 回答；如果资料不足，就说资料不足。"
                ),
            },
            {
                "role": "user",
                "content": f"context:\n{context}\n\nquestion:\n{question}",
            },
        ],
        stream=False,
    )
    return response.choices[0].message.content or ""


def generate_answer(question: str, chunks: list[dict]) -> str:
    # main.py 只调用这个统一入口，不关心背后是真实 DeepSeek 还是 mock。
    if get_provider_name() == "deepseek":
        return generate_deepseek_answer(question, chunks)
    return generate_mock_answer(question, chunks)

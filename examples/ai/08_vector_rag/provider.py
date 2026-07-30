import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
    # 没有真实 key 时走 mock，保证学习时先跑通完整向量 RAG 链路。
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        return None
    return api_key


def get_model_name() -> str:
    # 模型名来自 .env。把配置放在 .env，是为了避免把密钥和环境差异写死在代码里。
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def get_provider_name() -> str:
    if get_api_key():
        return "deepseek"
    return "mock"


def build_context(chunks: list[dict]) -> str:
    # sources 会被拼成 context，再交给模型回答。
    # 这一步是 RAG 的关键：模型不是凭空回答，而是基于检索到的资料回答。
    context_parts = []
    for index, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[source {index}] "
            f"document={chunk['document_title']}, "
            f"chunk_id={chunk['id']}, "
            f"score={chunk['score']}\n"
            f"{chunk['content']}"
        )
    return "\n\n".join(context_parts)


def generate_mock_answer(question: str, chunks: list[dict]) -> str:
    # mock 答案不调用真实模型，只告诉你向量检索拿到了哪些来源。
    if not chunks:
        return "[mock answer] 向量检索没有找到足够相关的资料。"

    titles = [chunk["document_title"] for chunk in chunks]
    scores = [str(chunk["score"]) for chunk in chunks]
    return (
        f"[mock answer] 问题是：{question}。"
        f"向量检索命中 {len(chunks)} 个片段，来源文档：{', '.join(titles)}，"
        f"相似度分数：{', '.join(scores)}。"
    )


def generate_deepseek_answer(question: str, chunks: list[dict]) -> str:
    # provider.py 可以类比成 Java 里的 Service：main.py 不直接关心外部模型 API 细节。
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
    # main.py 只调用统一入口，不关心背后是真实 DeepSeek 还是 mock。
    if get_provider_name() == "deepseek":
        return generate_deepseek_answer(question, chunks)
    return generate_mock_answer(question, chunks)

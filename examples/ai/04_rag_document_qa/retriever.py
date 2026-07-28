import re


def tokenize(text: str) -> list[str]:
    # 这是一个非常简化的分词函数。
    # 英文按单词切，数字也会保留；中文会按连续中文片段保留。
    # 真实 RAG 通常会使用 embedding，而不是这种关键词匹配。
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def score_chunk(question_tokens: list[str], chunk: dict) -> int:
    # 最简单的检索思路：
    # 问题里的词，在 chunk 里出现越多，分数越高。
    content = chunk["content"].lower()
    score = 0
    for token in question_tokens:
        if token and token in content:
            score += 1
    return score


def retrieve_relevant_chunks(
    question: str,
    chunks: list[dict],
    top_k: int = 3,
) -> list[dict]:
    # top_k 表示最多返回几个相关片段。
    # 这里返回的片段会作为“参考资料”传给模型。
    question_tokens = tokenize(question)
    scored_chunks: list[dict] = []

    for chunk in chunks:
        score = score_chunk(question_tokens, chunk)
        if score > 0:
            scored_chunk = dict(chunk)
            scored_chunk["score"] = score
            scored_chunks.append(scored_chunk)

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)
    return scored_chunks[:top_k]

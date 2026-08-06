import re


def tokenize(text: str) -> list[str]:
    # 这是一个非常简化的分词函数，负责把一句话切成可以匹配的“词”。
    # 英文按单词切；中文没有空格天然分词，教学版用相邻双字（bigram）近似切分。
    #
    # 为什么要 bigram：
    # 如果把一整句“报销流程是什么”当成一个 token，它很难在文档里原样出现。
    # 切成“报销、销流、流程、程是、是什么...”之后，“报销”“流程”就能在文档里命中，
    # 整句也能算分。缺点是有不少无意义双字（“程是”），真实项目用 embedding 解决。
    tokens: list[str] = []
    for run in re.findall(r"[a-zA-Z0-9]+", text):
        # 英文数字串直接作为一个 token。
        if run:
            tokens.append(run.lower())
    for run in re.findall(r"[一-鿿]+", text):
        # 中文连续片段切成相邻双字。
        if len(run) <= 2:
            tokens.append(run)
        else:
            for i in range(len(run) - 1):
                tokens.append(run[i : i + 2])
    return tokens


def score_chunk(question_tokens: list[str], chunk: dict) -> int:
    # 最简单的检索思路：
    # 问题里的词，在 chunk 里出现越多，分数越高。
    # 真实 RAG 会用向量相似度，这里先让你理解“相关 = 词出现得多”。
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
    # 这里返回的片段会作为“sources”传给 Agent，让最终回答有依据可查。
    question_tokens = tokenize(question)
    scored_chunks: list[dict] = []

    for chunk in chunks:
        score = score_chunk(question_tokens, chunk)
        if score > 0:
            # dict(chunk) 复制一份，避免污染原始数据。
            scored_chunk = dict(chunk)
            scored_chunk["score"] = score
            scored_chunks.append(scored_chunk)

    # 分数从高到低排序，取前 top_k 个。
    scored_chunks.sort(key=lambda item: item["score"], reverse=True)
    return scored_chunks[:top_k]

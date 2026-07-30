from embeddings import cosine_similarity, embed_text


def retrieve_relevant_chunks(
    question: str,
    chunks: list[dict],
    top_k: int = 3,
    min_score: float = 0.05,
) -> list[dict]:
    # 这是本模块和 04_rag_document_qa 最大的区别：
    # 04 用关键词是否出现打分；这里先把 question 转成向量，再和每个 chunk 的向量算相似度。
    question_embedding = embed_text(question)
    scored_chunks: list[dict] = []

    for chunk in chunks:
        score = cosine_similarity(question_embedding, chunk["embedding"])
        if score >= min_score:
            scored_chunk = dict(chunk)
            # embedding 很长，不适合作为 sources 原样返回给接口使用者。
            scored_chunk.pop("embedding", None)
            scored_chunk["score"] = round(score, 4)
            scored_chunks.append(scored_chunk)

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)
    return scored_chunks[:top_k]

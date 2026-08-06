def split_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    # RAG 不能直接把整篇长文档都塞给模型。
    # 常见做法是先把文档切成多个 chunk，检索时只取相关 chunk，避免上下文爆掉。
    #
    # chunk_size：每个片段大约多少字符。
    # overlap：相邻片段重叠多少字符，避免一句话刚好被切断后上下文丢失。
    cleaned_text = text.strip()
    if not cleaned_text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0

    while start < len(cleaned_text):
        # end 表示当前片段在原文里的结束位置。
        end = start + chunk_size
        chunk = cleaned_text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # 下一段从 end - overlap 开始，让相邻片段有一部分重复内容。
        start = end - overlap

    return chunks

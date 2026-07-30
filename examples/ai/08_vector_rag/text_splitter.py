def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    # RAG 不会把整篇文档直接塞给模型，而是先切成多个 chunk。
    # chunk 可以理解成“文档片段”。检索时只找最相关的几个片段，避免上下文过长。
    #
    # chunk_size：每个片段大约多少字符。
    # overlap：相邻片段重叠多少字符，避免一句话刚好被切断。
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
        end = start + chunk_size
        chunk = cleaned_text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # 下一段从 end - overlap 开始，让前后两个 chunk 保留一小段共同内容。
        start = end - overlap

    return chunks

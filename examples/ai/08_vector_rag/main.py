from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from db import create_document, init_db, list_all_chunks, list_chunks, list_documents
from embeddings import VECTOR_DIMENSION, embed_text, tokenize
from provider import generate_answer, get_model_name, get_provider_name
from retriever import retrieve_relevant_chunks
from text_splitter import split_text

app = FastAPI(title="Vector RAG")


class DocumentCreate(BaseModel):
    # 请求 DTO：客户端用 JSON 创建文档时，需要传 title 和 content。
    # 类比 Java 里的 CreateDocumentRequest，不是数据库表，也不是 ORM Entity。
    title: str
    content: str
    chunk_size: int = 500
    overlap: int = 80


class AskRequest(BaseModel):
    # question 是用户问题。
    # top_k 表示最多返回几个最相似的 chunk。
    # min_score 是最低相似度门槛，避免完全不相关的片段也被塞给模型。
    question: str
    top_k: int = 3
    min_score: float = 0.05


class EmbeddingDebugRequest(BaseModel):
    # 调试 DTO：用来观察“一段文本如何被分词、再变成向量”。
    # 这个接口不是生产功能，而是学习向量化 RAG 时的观察窗口。
    text: str


@app.on_event("startup")
def startup() -> None:
    # 服务启动时建表，让模块先能跑起来。
    # 后续如果要做生产化，仍然应该回到 07 模块学过的 Alembic 管理表结构。
    init_db()


@app.get("/health")
def health() -> dict:
    # embedding_provider 这里写 mock，是为了强调：当前 embedding 在本地生成，不调用真实外部服务。
    return {
        "status": "ok",
        "chat_provider": get_provider_name(),
        "chat_model": get_model_name(),
        "embedding_provider": "mock",
        "vector_dimension": VECTOR_DIMENSION,
    }


@app.post("/documents")
def ingest_document(payload: DocumentCreate) -> dict:
    # 完整入库链路：
    # 1. 接收文档。
    # 2. 切分成 chunks。
    # 3. 对每个 chunk 分词 tokenize。
    # 4. 把 token 转成 embedding 向量。
    # 5. 把 chunk 文本和 embedding 一起保存到 SQLite。
    try:
        chunks = split_text(
            text=payload.content,
            chunk_size=payload.chunk_size,
            overlap=payload.overlap,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if not chunks:
        raise HTTPException(status_code=400, detail="Document content is empty")

    chunk_vectors = []
    for chunk in chunks:
        # embed_text(chunk) 内部会先调用 tokenize(chunk)，再把 tokens 转成向量。
        # 这里不单独保存 tokens，是因为检索阶段真正需要比较的是 embedding。
        chunk_vectors.append({"content": chunk, "embedding": embed_text(chunk)})

    return create_document(title=payload.title, chunk_vectors=chunk_vectors)


@app.post("/documents/upload")
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    chunk_size: int = Form(500),
    overlap: int = Form(80),
) -> dict:
    # Form(...) 表示参数来自 multipart/form-data 表单。
    # UploadFile 用于接收文件上传；这和 JSON 请求体是两种不同的输入来源。
    file_bytes = await file.read()
    try:
        content = file_bytes.decode("utf-8")
        chunks = split_text(text=content, chunk_size=chunk_size, overlap=overlap)
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="Only UTF-8 text files are supported") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if not chunks:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    chunk_vectors = []
    for chunk in chunks:
        # 上传文件和 JSON 文档走同一条向量化链路：chunk -> token -> embedding。
        chunk_vectors.append({"content": chunk, "embedding": embed_text(chunk)})

    result = create_document(title=title, chunk_vectors=chunk_vectors)
    result["filename"] = file.filename
    return result


@app.get("/documents")
def get_documents() -> dict:
    # 查看已经入库的文档，以及每篇文档有多少个 chunk。
    return {"items": list_documents()}


@app.get("/documents/{document_id}/chunks")
def get_document_chunks(document_id: int) -> dict:
    # document_id 来自路径参数，例如 /documents/1/chunks 里的 1。
    chunks = list_chunks(document_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found or has no chunks")
    return {"items": chunks}


@app.post("/debug/embedding")
def debug_embedding(payload: EmbeddingDebugRequest) -> dict:
    # 这个接口专门用来拆开观察 embedding 生成过程。
    # 正常业务接口不会把 tokens 和完整向量都返回给用户；这里是为了学习和调试。
    tokens = tokenize(payload.text)
    embedding = embed_text(payload.text)
    return {
        "text": payload.text,
        "tokens": tokens,
        "token_count": len(tokens),
        "embedding_preview": embedding[:8],
        "embedding_dimension": len(embedding),
    }


@app.post("/ask")
def ask(payload: AskRequest) -> dict:
    # 向量化 RAG 的核心接口：
    # 1. 读取数据库里的所有 chunk embedding。
    # 2. 把 question 分词并转成 question embedding。
    # 3. 用 cosine similarity 找最相似的 top_k 个 chunks。
    # 4. 把检索结果交给 mock 或 DeepSeek 生成答案。
    if payload.top_k <= 0:
        raise HTTPException(status_code=400, detail="top_k must be greater than 0")

    all_chunks = list_all_chunks()
    if not all_chunks:
        raise HTTPException(status_code=400, detail="No documents have been ingested")

    relevant_chunks = retrieve_relevant_chunks(
        question=payload.question,
        chunks=all_chunks,
        top_k=payload.top_k,
        min_score=payload.min_score,
    )
    answer = generate_answer(question=payload.question, chunks=relevant_chunks)

    return {
        "question": payload.question,
        "answer": answer,
        "sources": relevant_chunks,
        "chat_provider": get_provider_name(),
        "chat_model": get_model_name(),
        "embedding_provider": "mock",
    }

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from db import create_document, init_db, list_all_chunks, list_chunks, list_documents
from provider import generate_answer, get_model_name, get_provider_name
from retriever import retrieve_relevant_chunks
from text_splitter import split_text

app = FastAPI(title="RAG Document QA")


class DocumentCreate(BaseModel):
    # 请求 DTO：用 JSON 创建文档时，客户端需要传 title 和 content。
    # 类比 Java 里的 CreateDocumentRequest。
    title: str
    content: str
    chunk_size: int = 500
    overlap: int = 80


class AskRequest(BaseModel):
    # question 是用户问题。
    # top_k 表示最多检索几个相关文本片段。
    question: str
    top_k: int = 3


@app.on_event("startup")
def startup() -> None:
    # 服务启动时创建 documents 和 chunks 两张表。
    init_db()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
    }


@app.post("/documents")
def ingest_document(payload: DocumentCreate) -> dict:
    # 1. 接收一整篇文本。
    # 2. 调用 split_text 切成 chunks。
    # 3. 把文档和 chunks 保存到 SQLite。
    chunks = split_text(
        text=payload.content,
        chunk_size=payload.chunk_size,
        overlap=payload.overlap,
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="Document content is empty")

    return create_document(title=payload.title, chunks=chunks)


@app.post("/documents/upload")
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    chunk_size: int = Form(500),
    overlap: int = Form(80),
) -> dict:
    # UploadFile 用于接收文件上传。
    # Form(...) 表示这个参数来自 multipart/form-data 表单，而不是 JSON。
    file_bytes = await file.read()
    content = file_bytes.decode("utf-8")
    chunks = split_text(text=content, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    result = create_document(title=title, chunks=chunks)
    result["filename"] = file.filename
    return result


@app.get("/documents")
def get_documents() -> dict:
    # 查看已经入库的文档。
    return {"items": list_documents()}


@app.get("/documents/{document_id}/chunks")
def get_document_chunks(document_id: int) -> dict:
    # 查看一个文档切分后的 chunks。
    chunks = list_chunks(document_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found or has no chunks")
    return {"items": chunks}


@app.post("/ask")
def ask(payload: AskRequest) -> dict:
    # 这是 RAG 的核心接口：
    # 1. 读取所有 chunks。
    # 2. 根据 question 检索最相关的 top_k 个 chunks。
    # 3. 把检索结果交给 mock 或 DeepSeek 生成答案。
    all_chunks = list_all_chunks()
    if not all_chunks:
        raise HTTPException(status_code=400, detail="No documents have been ingested")

    relevant_chunks = retrieve_relevant_chunks(
        question=payload.question,
        chunks=all_chunks,
        top_k=payload.top_k,
    )
    answer = generate_answer(question=payload.question, chunks=relevant_chunks)

    return {
        "question": payload.question,
        "answer": answer,
        "sources": relevant_chunks,
        "provider": get_provider_name(),
        "model": get_model_name(),
    }

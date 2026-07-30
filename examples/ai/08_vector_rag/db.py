import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("vector_rag.db")


def get_connection() -> sqlite3.Connection:
    # sqlite3 是 Python 标准库。
    # 本模块先用 SQLite 保存 embedding，目的是让你先看懂向量检索链路。
    # 后续生产项目里，可以把 chunks 表替换成 pgvector、Milvus、Qdrant 等向量库。
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    # documents 表保存原始文档信息。
    # chunks 表保存切分后的文本片段，并多了 embedding_json 字段。
    # embedding_json 用 JSON 字符串保存向量；这不是高性能做法，但最容易观察和理解。
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
            """
        )


def create_document(title: str, chunk_vectors: list[dict]) -> dict:
    # chunk_vectors 里的每一项包含：
    # - content：文本片段
    # - embedding：这个片段对应的向量
    #
    # 类比 Java：documents 是 Document Entity，chunks 是 DocumentChunk Entity。
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO documents (title) VALUES (?)",
            (title,),
        )
        document_id = cursor.lastrowid

        for index, item in enumerate(chunk_vectors):
            connection.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, content, embedding_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    document_id,
                    index,
                    item["content"],
                    json.dumps(item["embedding"], ensure_ascii=False),
                ),
            )

        row = connection.execute(
            """
            SELECT id, title, created_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

        result = dict(row)
        result["chunk_count"] = len(chunk_vectors)
        return result


def list_documents() -> list[dict]:
    # 返回文档列表，并统计每个文档切成了多少个 chunk。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                documents.id,
                documents.title,
                documents.created_at,
                COUNT(chunks.id) AS chunk_count
            FROM documents
            LEFT JOIN chunks ON chunks.document_id = documents.id
            GROUP BY documents.id
            ORDER BY documents.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def decode_embedding(embedding_json: str) -> list[float]:
    # 数据库里只能直接保存文本、数字等基础类型。
    # 所以向量入库时转成 JSON 字符串，读取时再转回 list[float]。
    raw_values = json.loads(embedding_json)
    return [float(value) for value in raw_values]


def list_chunks(document_id: int) -> list[dict]:
    # 查看某个文档的 chunk，并返回 embedding_preview。
    # preview 只展示前 6 个数字，避免接口返回太长，不方便在 /docs 里观察。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, document_id, chunk_index, content, embedding_json, created_at
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,),
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        embedding = decode_embedding(item.pop("embedding_json"))
        item["embedding_preview"] = embedding[:6]
        item["embedding_dimension"] = len(embedding)
        items.append(item)
    return items


def list_all_chunks() -> list[dict]:
    # 向量检索阶段会读取所有 chunks 和它们的 embedding。
    # 这相当于一个“教学版向量库”：能理解链路，但不是生产性能。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                chunks.id,
                chunks.document_id,
                chunks.chunk_index,
                chunks.content,
                chunks.embedding_json,
                documents.title AS document_title
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            ORDER BY chunks.id ASC
            """
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["embedding"] = decode_embedding(item.pop("embedding_json"))
        items.append(item)
    return items

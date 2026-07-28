import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("rag_documents.db")


def get_connection() -> sqlite3.Connection:
    # sqlite3 是 Python 标准库。
    # 这里仍然使用 SQLite，是为了让你先专注 RAG 流程，不被数据库安装打断。
    connection = sqlite3.connect(DB_PATH)
    # row_factory 让查询结果可以像字典一样按字段名读取。
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    # documents 表保存“原始文档”的基本信息。
    # chunks 表保存“切分后的文本片段”，后续检索时主要查 chunks。
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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
            """
        )


def create_document(title: str, chunks: list[str]) -> dict:
    # 先保存 documents，再保存它对应的 chunks。
    # 类比 Java 里先保存 Document Entity，再保存一批 Chunk Entity。
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO documents (title) VALUES (?)",
            (title,),
        )
        document_id = cursor.lastrowid

        for index, chunk in enumerate(chunks):
            connection.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, content)
                VALUES (?, ?, ?)
                """,
                (document_id, index, chunk),
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
        result["chunk_count"] = len(chunks)
        return result


def list_documents() -> list[dict]:
    # 返回文档列表，并附带每个文档有多少个 chunk。
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


def list_chunks(document_id: int) -> list[dict]:
    # 查看某个文档被切成了哪些片段。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, document_id, chunk_index, content, created_at
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_all_chunks() -> list[dict]:
    # 检索阶段会扫描所有 chunks。
    # 真实项目里这里会换成向量数据库检索，而不是全表扫描。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                chunks.id,
                chunks.document_id,
                chunks.chunk_index,
                chunks.content,
                documents.title AS document_title
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            ORDER BY chunks.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

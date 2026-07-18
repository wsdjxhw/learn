import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("chat_history.db")


def get_connection() -> sqlite3.Connection:
    # sqlite3 是 Python 标准库，适合学习阶段做本地持久化。
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    # sessions 存会话，messages 存每条聊天消息。
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
            """
        )


def create_session(title: str) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO sessions (title) VALUES (?)",
            (title,),
        )
        session_id = cursor.lastrowid
        row = connection.execute(
            "SELECT id, title, created_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return dict(row)


def list_sessions() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, created_at FROM sessions ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_session(session_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, title, created_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def add_message(session_id: int, role: str, content: str) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        message_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        return dict(row)


def list_messages(session_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_messages_for_model(session_id: int) -> list[dict]:
    # 模型只需要 role 和 content，不需要数据库里的 id、时间等字段。
    messages = list_messages(session_id)
    return [
        {"role": message["role"], "content": message["content"]}
        for message in messages
    ]

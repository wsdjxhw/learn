import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# database.py 也主动读取 .env，是为了让数据库路径配置在本地运行和 Docker 运行时都生效。
# 注意 main.py 虽然也会 load_dotenv，但 main.py 导入 database.py 时，database.py 的顶层代码会先执行。
# 如果这里不读取 .env，CHAT_DB_PATH 这种数据库相关配置就可能太晚才被加载。
load_dotenv(dotenv_path=BASE_DIR / ".env")


def get_database_path() -> Path:
    # 默认仍然使用模块目录下的 chat_ui.db，保持前端模块原来的本地学习体验。
    # Docker 部署时会通过 CHAT_DB_PATH=/app/data/chat_ui.db 把数据库放到数据卷里。
    # 这样容器删除再重建时，只要数据卷还在，聊天历史就不会丢。
    configured_path = os.getenv("CHAT_DB_PATH")
    if not configured_path:
        return BASE_DIR / "chat_ui.db"

    path = Path(configured_path)
    if not path.is_absolute():
        # 如果 .env 写的是相对路径，就按当前模块目录解释。
        # 这比按启动命令所在目录解释更稳定，初学者不容易因为 cd 到不同目录而找不到数据库。
        path = BASE_DIR / path

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


DB_PATH = get_database_path()


def get_connection() -> sqlite3.Connection:
    # 本模块用 SQLite 保存前端页面需要展示的数据：
    # 会话列表、消息历史、后台任务状态和 RAG sources。
    # 这样刷新页面后，刚才的会话不会立刻丢失。
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    # sessions：会话列表。
    # messages：每个会话里的 user / assistant 消息。
    # chat_tasks：前端发送消息后拿到的后台任务。
    # task_sources：任务完成后展示在右侧面板里的资料来源。
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                user_message TEXT NOT NULL,
                result_message_id INTEGER,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                snippet TEXT NOT NULL,
                score REAL NOT NULL,
                FOREIGN KEY (task_id) REFERENCES chat_tasks (id)
            )
            """
        )


def create_session(title: str) -> dict:
    # 创建会话。类比真实聊天产品里的“新建对话”。
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO sessions (title) VALUES (?)",
            (title,),
        )
        session_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        return dict(row)


def ensure_default_session() -> dict:
    # 页面第一次打开时，如果没有任何会话，就创建一个默认会话。
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM sessions
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
    if row:
        return dict(row)
    return create_session("学习聊天")


def list_sessions() -> list[dict]:
    # 会话列表要带上 message_count，前端侧边栏可以显示每个会话大概有多少消息。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                sessions.id,
                sessions.title,
                sessions.created_at,
                sessions.updated_at,
                COUNT(messages.id) AS message_count
            FROM sessions
            LEFT JOIN messages ON messages.session_id = sessions.id
            GROUP BY sessions.id
            ORDER BY sessions.updated_at DESC, sessions.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_session(session_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


def update_session_title(session_id: int, title: str) -> dict | None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE sessions
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, session_id),
        )
    return get_session(session_id)


def touch_session(session_id: int) -> None:
    # 每次新增消息后更新会话时间，让最近对话排在列表前面。
    with get_connection() as connection:
        connection.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )


def create_message(session_id: int, role: str, content: str) -> dict:
    # role 只在接口层约定 user / assistant。
    # 真实项目可以进一步做枚举校验。
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, role, content),
        )
        message_id = cursor.lastrowid
        connection.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
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


def list_recent_messages(session_id: int, limit: int = 8) -> list[dict]:
    # 短期记忆不是只把历史消息显示在页面上。
    # 生成 assistant 回复前，后端还要把最近几条消息读出来，作为上下文交给 provider。
    #
    # limit 控制最多带多少条历史，避免一次会话太长时 prompt 无限增长。
    # 真实项目还会按 token 数裁剪，而不是简单按消息条数裁剪。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()

    # SQL 为了取最近 N 条用了倒序；返回给 provider 前再翻回正序，
    # 这样模型看到的上下文顺序仍然是从旧到新。
    return [dict(row) for row in reversed(rows)]


def create_chat_task(session_id: int, user_message: str) -> dict:
    # 前端发送消息后，后端先创建任务并返回 task_id。
    # 页面随后轮询 GET /api/tasks/{task_id}，观察 pending -> running -> succeeded。
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO chat_tasks (session_id, status, user_message)
            VALUES (?, ?, ?)
            """,
            (session_id, "pending", user_message),
        )
        task_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT id, session_id, status, user_message, result_message_id, error_message, created_at, updated_at
            FROM chat_tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
        return dict(row)


def mark_task_running(task_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE chat_tasks
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("running", task_id),
        )


def mark_task_succeeded(task_id: int, result_message_id: int, sources: list[dict]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE chat_tasks
            SET status = ?, result_message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("succeeded", result_message_id, task_id),
        )
        for source in sources:
            connection.execute(
                """
                INSERT INTO task_sources (task_id, title, snippet, score)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, source["title"], source["snippet"], source["score"]),
            )


def mark_task_failed(task_id: int, error_message: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE chat_tasks
            SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("failed", error_message, task_id),
        )


def get_task(task_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, session_id, status, user_message, result_message_id, error_message, created_at, updated_at
            FROM chat_tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None

        sources = connection.execute(
            """
            SELECT id, title, snippet, score
            FROM task_sources
            WHERE task_id = ?
            ORDER BY score DESC, id ASC
            """,
            (task_id,),
        ).fetchall()

    task = dict(row)
    task["sources"] = [dict(source) for source in sources]
    return task

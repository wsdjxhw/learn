import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("background_tasks.db")


def get_connection() -> sqlite3.Connection:
    # SQLite 仍然用于学习阶段。
    # 这个模块重点是“任务状态流转”，不是数据库安装和部署。
    connection = sqlite3.connect(DB_PATH)
    # row_factory 让查询结果可以 dict(row)，方便接口直接返回 JSON。
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    # summary_tasks 表保存后台任务。
    #
    # status 是本模块最重要的字段：
    # pending：任务刚创建，还没开始处理。
    # running：后台 worker 正在处理。
    # succeeded：处理成功，可以读取 result。
    # failed：处理失败，可以读取 error。
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS summary_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                input_text TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_summary_task(input_text: str) -> dict:
    # 创建任务时只保存输入文本，状态先设为 pending。
    # 类比 Java 里创建一个 Task Entity，然后返回 task_id。
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO summary_tasks (status, input_text)
            VALUES (?, ?)
            """,
            ("pending", input_text),
        )
        task_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT id, status, input_text, result, error, created_at, updated_at
            FROM summary_tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
        return dict(row)


def get_summary_task(task_id: int) -> dict | None:
    # 根据 task_id 查询单个任务。
    # 如果返回 None，接口层会把它转换成 HTTP 404。
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, status, input_text, result, error, created_at, updated_at
            FROM summary_tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def list_summary_tasks() -> list[dict]:
    # 查询任务列表，按 id 倒序显示最新任务。
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, status, input_text, result, error, created_at, updated_at
            FROM summary_tasks
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def mark_task_running(task_id: int) -> None:
    # worker 开始处理任务时，把状态改成 running。
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE summary_tasks
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("running", task_id),
        )


def mark_task_succeeded(task_id: int, result: str) -> None:
    # worker 成功完成任务时，保存 result。
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE summary_tasks
            SET status = ?, result = ?, error = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("succeeded", result, task_id),
        )


def mark_task_failed(task_id: int, error: str) -> None:
    # worker 处理失败时，保存错误信息。
    # 真实项目里 error 可能要区分给用户看的信息和内部日志。
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE summary_tasks
            SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("failed", error, task_id),
        )

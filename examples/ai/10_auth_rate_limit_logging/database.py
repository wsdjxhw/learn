import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("auth_rate_limit_logging.db")


def get_connection() -> sqlite3.Connection:
    # 本模块用 SQLite 保存请求日志、错误日志和模型调用日志。
    # 目标不是做高性能日志系统，而是让你能在 /docs 里观察“请求发生后留下了什么记录”。
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    # request_logs：记录每次 HTTP 请求。
    # error_logs：记录统一错误响应产生的错误。
    # model_call_logs：记录模型调用和教学版成本估算。
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                api_key_hash TEXT,
                client_host TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                api_key_hash TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS model_call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                success INTEGER NOT NULL,
                prompt_chars INTEGER NOT NULL,
                reply_chars INTEGER NOT NULL,
                estimated_input_tokens INTEGER NOT NULL,
                estimated_output_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL,
                error_message TEXT
            )
            """
        )


def create_request_log(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    api_key_hash: str | None,
    client_host: str | None,
) -> None:
    # 只保存 api_key_hash，不保存原始 API Key。
    # 这是一个重要安全习惯：日志里不要留下可直接使用的密钥。
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO request_logs (
                method, path, status_code, duration_ms, api_key_hash, client_host
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (method, path, status_code, duration_ms, api_key_hash, client_host),
        )


def create_error_log(
    path: str,
    status_code: int,
    error_type: str,
    message: str,
    api_key_hash: str | None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO error_logs (
                path, status_code, error_type, message, api_key_hash
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (path, status_code, error_type, message, api_key_hash),
        )


def create_model_call_log(
    provider: str,
    model: str,
    success: bool,
    prompt_chars: int,
    reply_chars: int,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
    estimated_cost_usd: float,
    error_message: str | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO model_call_logs (
                provider,
                model,
                success,
                prompt_chars,
                reply_chars,
                estimated_input_tokens,
                estimated_output_tokens,
                estimated_cost_usd,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider,
                model,
                1 if success else 0,
                prompt_chars,
                reply_chars,
                estimated_input_tokens,
                estimated_output_tokens,
                estimated_cost_usd,
                error_message,
            ),
        )


def list_request_logs(limit: int = 20) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, method, path, status_code, duration_ms, api_key_hash, client_host
            FROM request_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_error_logs(limit: int = 20) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, path, status_code, error_type, message, api_key_hash
            FROM error_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_model_call_logs(limit: int = 20) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                provider,
                model,
                success,
                prompt_chars,
                reply_chars,
                estimated_input_tokens,
                estimated_output_tokens,
                estimated_cost_usd,
                error_message
            FROM model_call_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_cost_summary() -> dict:
    # 这里是教学版成本统计，用估算 token 数和固定单价演示“成本记录”该怎么落表。
    # 真实项目要按模型服务商的实际 usage 和价格计算。
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS call_count,
                SUM(success) AS success_count,
                SUM(estimated_input_tokens) AS input_tokens,
                SUM(estimated_output_tokens) AS output_tokens,
                SUM(estimated_cost_usd) AS estimated_cost_usd
            FROM model_call_logs
            """
        ).fetchone()
        result = dict(row)
        return {
            "call_count": result["call_count"] or 0,
            "success_count": result["success_count"] or 0,
            "input_tokens": result["input_tokens"] or 0,
            "output_tokens": result["output_tokens"] or 0,
            "estimated_cost_usd": round(result["estimated_cost_usd"] or 0.0, 6),
        }

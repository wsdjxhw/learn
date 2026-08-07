"""
audit.py —— 审计日志写入

职责：把每一次数据库操作尝试写成一行日志（DatabaseOpLog 表）。

关键设计（真实项目重要）：
- 不只记录成功操作，连"被权限拦截 / 参数校验失败 / 被人工拒绝"都要记。
  审计的目的不是表扬谁，而是回答："谁、在什么时间、想对数据库做什么"。
  只有把所有尝试都记下来，才能追溯越权和误操作。
"""

import json

from database import SessionLocal
from models import DatabaseOpLog


def log_operation(
    api_key: str,
    role: str,
    tool_name: str,
    args: dict,
    status: str,
    sql_text: str | None = None,
    row_count: int | None = None,
    confirmation_id: int | None = None,
    result_summary: str | None = None,
    error: str | None = None,
):
    """写一条审计日志。参数几乎对应 DatabaseOpLog 的每一列。

    status 的可选值（和确认单/工具结果对应）：
      requested  -> 发起了一个写操作（创建了确认单，还没执行）
      executed   -> 真正执行成功了
      rejected   -> 被人工拒绝了
      blocked    -> 权限不足被拦下
      failed     -> 校验失败 / 业务规则失败 / 异常
    """
    # 新开一个独立的 Session 来写日志。为什么不用调用方的事务？
    # 因为如果业务操作失败导致事务回滚，日志不能跟着回滚掉——否则就查不到
    # 这次失败尝试了。日志必须是"独立的、无论如何都要落库"的。
    with SessionLocal() as db:
        log = DatabaseOpLog(
            api_key=api_key,
            role=role,
            tool_name=tool_name,
            args_json=json.dumps(args, ensure_ascii=False),
            sql_text=sql_text,
            row_count=row_count,
            status=status,
            confirmation_id=confirmation_id,
            result_summary=result_summary,
            error=error,
        )
        db.add(log)
        db.commit()

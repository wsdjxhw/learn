"""
tests/test_safety.py —— 数据库智能体的安全测试

为什么要有安全测试？数据库智能体最大的风险是"模型/用户拿到 SQL 接口后乱来"。
这些测试把最核心的安全底线固化成自动化检查：
  1. SQL 安全校验：破坏性语句、多语句、系统表必须被拦。
  2. 权限边界：viewer 不能碰写工具。
  3. 写操作确认门：写操作先生成确认单，批准后才真正执行。
  4. 业务规则：不能删履约中的订单。

运行方式（在本模块目录下）：
  python -m pytest tests/ -v

注意：测试不调用任何模型、不联网、不需要 API Key。
"""

import os
import pathlib
import sys

# ============================================================
# 关键步骤：必须在导入任何 app 模块之前，把数据库指到一个独立的测试文件。
# 否则测试会污染你在用正式数据跑出来的 demo 数据库。
# 同时每次运行先删掉旧测试库，保证用例可以反复跑、结果确定。
# ============================================================
MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = MODULE_DIR / "test_agent_database.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

# 把模块目录加入 sys.path，这样测试里才能 import app 的各个文件
sys.path.insert(0, str(MODULE_DIR))

import pytest  # noqa: E402

from database import SessionLocal, init_db  # noqa: E402
from errors import SqlSafetyError  # noqa: E402
from models import DatabaseOpLog, Order  # noqa: E402
from seed import seed_if_empty  # noqa: E402
from settings import settings  # noqa: E402
from sql_safety import validate_readonly_sql  # noqa: E402
from sqlalchemy import select  # noqa: E402
from tool_registry import approve_confirmation, execute_tool  # noqa: E402

# 准备干净的测试数据
init_db()
seed_if_empty()

VIEWER = settings.viewer_api_key
OPERATOR = settings.operator_api_key


# ---------- 1. SQL 安全校验 ----------


def test_sql_safety_blocks_drop():
    """DROP 这种破坏性语句必须被拦。"""
    with pytest.raises(SqlSafetyError):
        validate_readonly_sql("DROP TABLE orders")


def test_sql_safety_blocks_multi_statement():
    """分号 = 多条语句，必须被拦（防止 SELECT 后偷偷跟 DELETE）。"""
    with pytest.raises(SqlSafetyError):
        validate_readonly_sql("SELECT * FROM orders; DELETE FROM orders")


def test_sql_safety_blocks_system_table():
    """系统表不该被查询者访问（信息泄露面）。"""
    with pytest.raises(SqlSafetyError):
        validate_readonly_sql("SELECT name FROM sqlite_master")


def test_sql_safety_adds_limit():
    """没有 LIMIT 的查询会被自动补上，防止全表扫描打垮数据库。"""
    sql = validate_readonly_sql("SELECT * FROM orders")
    assert "LIMIT" in sql.upper()


def test_sql_safety_allows_simple_select():
    """正常的只读查询应该放行（并补 LIMIT）。"""
    sql = validate_readonly_sql("SELECT id, amount FROM orders WHERE amount > 100")
    assert "LIMIT" in sql.upper()


# ---------- 2. 权限边界 ----------


def test_viewer_can_query():
    """viewer 可以用只读查询工具。"""
    result = execute_tool("query_orders", {}, "viewer", VIEWER)
    assert result.status == "success"
    assert result.data["count"] >= 1


def test_viewer_cannot_write():
    """viewer 试图调用写工具必须被拦（blocked），并且要记审计。"""
    result = execute_tool("delete_order", {"order_id": 1}, "viewer", VIEWER)
    assert result.status == "blocked"

    # 越权尝试必须出现在审计日志里
    with SessionLocal() as db:
        blocked = db.scalars(
            select(DatabaseOpLog).where(DatabaseOpLog.status == "blocked")
        ).all()
    assert len(blocked) >= 1


# ---------- 3. 写操作确认门 ----------


def test_write_creates_confirmation_not_execute():
    """operator 发起写操作：先创建确认单，订单本身没被改。

    用订单2（seed 状态 paid），目标 shipped，是状态机允许的合法流转。
    """
    result = execute_tool(
        "update_order_status", {"order_id": 2, "new_status": "shipped"}, "operator", OPERATOR
    )
    assert result.status == "awaiting_confirmation"
    assert result.confirmation_id is not None

    # 确认前，订单状态必须没变（仍然是 paid）
    with SessionLocal() as db:
        order = db.get(Order, 2)
    assert order.status == "paid"


def test_approve_executes_write():
    """批准确认单后，写操作才真正生效。

    用订单4（seed 状态 pending），目标 paid，是合法流转（pending -> paid）。
    """
    result = execute_tool(
        "update_order_status", {"order_id": 4, "new_status": "paid"}, "operator", OPERATOR
    )
    assert result.status == "awaiting_confirmation"

    exec_result, req = approve_confirmation(result.confirmation_id, "operator", OPERATOR)
    assert exec_result.status == "success"
    assert req.status == "executed"

    with SessionLocal() as db:
        order = db.get(Order, 4)
    assert order.status == "paid"


# ---------- 4. 业务规则 ----------


def test_business_rule_blocks_deleting_paid_order():
    """业务规则：不能删除已付款的订单（seed 里订单7是 paid）。"""
    result = execute_tool("delete_order", {"order_id": 7}, "operator", OPERATOR, require_confirm=False)
    assert result.status == "failed"
    assert "不能删除" in result.message

"""
tool_registry.py —— 工具注册表 + 执行中枢（本模块的心脏）

职责：
1. 工具注册表：把"有哪些工具、各自参数长什么样、需要什么权限、是不是写操作、
   要不要确认"集中定义在 TOOLS 字典里。这相当于后端的"工具白名单"——
   模型只能从这份名单里选工具，名单外的函数它永远够不到。
2. 执行中枢 execute_tool：无论谁（Agent 自动调用 / 手动 /tool/run 调用）
   执行工具，都必须经过同一套流程：权限检查 -> 参数校验 -> 写操作确认门
   -> 真正执行 -> 审计日志。所有工具共用一个入口，才保证"没有漏网之鱼"。

完整执行流程（初学者按这个顺序读）：
   execute_tool()
     1) 工具是否存在
     2) 角色权限是否够（security.has_role）
     3) Pydantic 参数校验（schemas 里的 arg_model）
     4) 如果是写操作且要确认：创建确认单，返回"等待确认"，不真正执行
     5) 否则：调用 handler 真正执行
     6) 无论哪一步，都写一条审计日志（audit.log_operation）
"""

import json
from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

import confirmation
from audit import log_operation
from errors import BusinessRuleError
from models import ORDER_STATUS_CN
from schemas import (
    CreateOrderArgs,
    DeleteOrderArgs,
    QueryCustomersArgs,
    QueryOrdersArgs,
    QueryStatsArgs,
    RunSqlArgs,
    UpdateOrderStatusArgs,
)
from query_tools import handle_query_customers, handle_query_orders, handle_query_stats
from write_tools import handle_create_order, handle_delete_order, handle_update_order_status
from sql_safety import handle_run_sql_readonly
from security import has_role


@dataclass
class ToolMeta:
    """一个工具的元信息（定义"这个工具是什么"）。"""

    name: str                      # 工具名，Agent 和手动调用都用它
    description: str               # 给模型看的描述，决定模型何时选它（重要！）
    arg_model: type[BaseModel]     # 参数校验模型（schemas 里定义的）
    min_role: str                  # 最低需要的角色 viewer/operator
    risk: str                      # 风险等级 low/medium/high
    is_write: bool                 # 是否写操作（改数据库）
    requires_confirmation: bool    # 是否必须人工确认
    handler: Callable              # 真正干活的函数，签名 (validated_args, role) -> dict


@dataclass
class ToolResult:
    """一次工具执行的结果（统一返回结构）。

    status 有 4 种：
      success                已执行成功
      awaiting_confirmation  写操作已创建确认单，等待审批
      blocked                权限不足被拦下
      failed                 校验失败 / 业务规则失败 / 异常
    """

    status: str
    message: str
    data: dict | None = None
    confirmation_id: int | None = None


# ---------- 工具注册表：所有工具的唯一定义处 ----------
# 新增一个工具 = 在这里加一行，这就是"工具即配置"的思想。
TOOLS: dict[str, ToolMeta] = {
    # ============ 只读查询工具（viewer 即可用，直接执行） ============
    "query_customers": ToolMeta(
        name="query_customers",
        description="查询客户列表。可按城市（如北京）、等级（vip/normal）、姓名关键词过滤。"
                    "当用户问'有哪些客户/北京的客户/谁下了单'时使用。",
        arg_model=QueryCustomersArgs,
        min_role="viewer",
        risk="low",
        is_write=False,
        requires_confirmation=False,
        handler=handle_query_customers,
    ),
    "query_orders": ToolMeta(
        name="query_orders",
        description="查询订单列表，带客户姓名。可按状态（pending/paid/shipped/completed/cancelled）、"
                    "客户id、最低金额过滤。当用户问'查订单/某客户买了什么/多少金额的订单'时使用。",
        arg_model=QueryOrdersArgs,
        min_role="viewer",
        risk="low",
        is_write=False,
        requires_confirmation=False,
        handler=handle_query_orders,
    ),
    "query_order_stats": ToolMeta(
        name="query_order_stats",
        description="统计订单：按状态或按城市统计订单数量和总金额。"
                    "当用户问'统计/总共多少单/各状态订单/总金额/哪个城市买得多'时使用。",
        arg_model=QueryStatsArgs,
        min_role="viewer",
        risk="low",
        is_write=False,
        requires_confirmation=False,
        handler=handle_query_stats,
    ),
    "run_sql_readonly": ToolMeta(
        name="run_sql_readonly",
        description="执行一段只读 SQL 查询（只能 SELECT/WITH，会自动加 LIMIT 并做安全校验）。"
                    "当用户明确要求用 SQL 查询、或前面工具满足不了复杂查询时使用。"
                    "禁止用它做任何写操作。",
        arg_model=RunSqlArgs,
        min_role="operator",   # 自由 SQL 比结构化工具危险，只开放给操作员及以上
        risk="medium",
        is_write=False,
        requires_confirmation=False,
        handler=handle_run_sql_readonly,
    ),
    # ============ 写入工具（operator 才能用，且必须人工确认） ============
    "create_order": ToolMeta(
        name="create_order",
        description="创建一条新订单（状态为 pending）。需要客户id、商品名、金额。"
                    "当用户要求'下单/创建订单/新增订单/买一个X'时使用。注意：这是写操作，需要人工确认。",
        arg_model=CreateOrderArgs,
        min_role="operator",
        risk="medium",
        is_write=True,
        requires_confirmation=True,
        handler=handle_create_order,
    ),
    "update_order_status": ToolMeta(
        name="update_order_status",
        description="把某订单状态改为新状态（pending/paid/shipped/completed/cancelled），"
                    "自动按状态机校验合法性。当用户要求'发货/改成已付款/更新订单状态'时使用。"
                    "注意：这是写操作，需要人工确认。",
        arg_model=UpdateOrderStatusArgs,
        min_role="operator",
        risk="medium",
        is_write=True,
        requires_confirmation=True,
        handler=handle_update_order_status,
    ),
    "delete_order": ToolMeta(
        name="delete_order",
        description="删除某订单（只有 pending/cancelled 状态允许删）。"
                    "当用户要求'删除订单/删掉订单X'时使用。注意：这是写操作，需要人工确认，风险较高。",
        arg_model=DeleteOrderArgs,
        min_role="operator",
        risk="high",
        is_write=True,
        requires_confirmation=True,
        handler=handle_delete_order,
    ),
}


def get_tool(tool_name: str) -> ToolMeta | None:
    """按名字取工具，不存在返回 None。"""
    return TOOLS.get(tool_name)


def visible_tools_for_role(role: str) -> list[ToolMeta]:
    """返回某角色可见的工具列表（权限白名单的"可见性"层面）。"""
    return [t for t in TOOLS.values() if has_role(t.min_role, role)]


def execute_tool(
    tool_name: str,
    args: dict,
    role: str,
    api_key: str,
    *,
    require_confirm: bool = True,
    confirmation_id: int | None = None,
) -> ToolResult:
    """执行中枢：所有工具调用的唯一入口。

    参数说明：
      require_confirm=True  表示"走确认门"（Agent 发起 / 手动调用时用）
      require_confirm=False 表示"已确认过，直接执行"（审批人批准时用）
      confirmation_id       审批执行时带上确认单 id，写进审计日志
    """
    tool = TOOLS.get(tool_name)
    if tool is None:
        # 工具不存在：这本身也要记日志（可能是被攻击者伪造的工具名）
        log_operation(api_key, role, tool_name, args, "failed", error="未知工具")
        return ToolResult("failed", f"未知工具：{tool_name}")

    # ---------- 第 1 道门：权限 ----------
    if not has_role(tool.min_role, role):
        log_operation(api_key, role, tool_name, args, "blocked",
                      error=f"角色 {role} 无权使用该工具（需要至少 {tool.min_role}）")
        return ToolResult("blocked",
                          f"当前角色 {role} 无权调用 {tool_name}（需要至少 {tool.min_role} 角色）")

    # ---------- 第 2 道门：参数校验（Pydantic） ----------
    try:
        # **args 表示把字典按关键字展开传入，例如 {"order_id": 3} -> arg_model(order_id=3)
        validated = tool.arg_model(**args)
    except ValidationError as e:
        # 把 Pydantic 的错误信息精简成用户能看懂的样子（取前 3 条）
        first_errors = [
            {"field": err["loc"][0], "msg": err["msg"]} for err in e.errors()[:3]
        ]
        log_operation(api_key, role, tool_name, args, "failed",
                      error=f"参数校验失败：{first_errors}")
        return ToolResult("failed", f"参数校验失败：{first_errors}")

    # ---------- 第 3 道门：写操作人工确认 ----------
    if tool.is_write and tool.requires_confirmation and require_confirm:
        req = confirmation.create_request(tool_name, args, api_key, role)
        log_operation(api_key, role, tool_name, args, "requested",
                      confirmation_id=req.id,
                      result_summary=f"已创建确认单 #{req.id}，等待审批")
        return ToolResult(
            "awaiting_confirmation",
            f"写操作已创建确认单 #{req.id}，等待人工确认后才会真正执行",
            confirmation_id=req.id,
        )

    # ---------- 第 4 步：真正执行 ----------
    try:
        result = tool.handler(validated, role)
        # 查询工具返回的 dict 里带 sql / count，写工具带 message / order_id
        log_operation(
            api_key, role, tool_name, args, "executed",
            sql_text=result.get("sql"),
            row_count=result.get("count", 1),
            confirmation_id=confirmation_id,
            result_summary=result.get("message"),
        )
        return ToolResult("success", result.get("message", "执行成功"), data=result)
    except BusinessRuleError as e:
        # 业务规则失败：可给用户看的错误
        log_operation(api_key, role, tool_name, args, "failed",
                      confirmation_id=confirmation_id, error=str(e))
        return ToolResult("failed", str(e))
    except Exception as e:
        # 兜底异常：任何没预料到的问题都在这里接住，不让接口 500 崩掉
        log_operation(api_key, role, tool_name, args, "failed",
                      confirmation_id=confirmation_id, error=f"执行异常：{e}")
        return ToolResult("failed", f"执行异常：{e}")


def approve_confirmation(confirmation_id: int, role: str, api_key: str) -> tuple[ToolResult, object]:
    """批准一个确认单：校验后按快照参数真正执行写工具。

    返回 (ToolResult, 确认单 ORM 对象)。如果确认单不存在 / 不在 pending /
    审批人权限不足，直接抛 HTTPException（由 main.py 的接口层转成 4xx 响应）。
    """
    req = confirmation.get_request(confirmation_id)
    if req is None:
        raise HTTPException(status_code=404, detail=f"确认单 #{confirmation_id} 不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"确认单 #{confirmation_id} 当前状态是 {req.status}，只能批准 pending 状态的确认单")

    tool = TOOLS.get(req.tool_name)
    # 审批人也必须满足该工具的权限等级（防止低权限者审批高权限操作）
    if tool is None or not has_role(tool.min_role, role):
        log_operation(api_key, role, req.tool_name, {}, "blocked",
                      confirmation_id=confirmation_id,
                      error="审批人权限不足")
        confirmation.mark_status(confirmation_id, "failed", api_key, error="审批人权限不足")
        raise HTTPException(status_code=403, detail=f"角色 {role} 无权批准该操作")

    # 用发起时保存的参数快照执行，require_confirm=False 表示不再二次确认
    args = json.loads(req.args_json)
    result = execute_tool(
        req.tool_name, args, role, api_key,
        require_confirm=False, confirmation_id=confirmation_id,
    )

    if result.status == "success":
        confirmation.mark_status(confirmation_id, "executed", api_key, result_summary=result.message)
    else:
        confirmation.mark_status(confirmation_id, "failed", api_key, error=result.message)
    return result, confirmation.get_request(confirmation_id)


def reject_confirmation(confirmation_id: int, role: str, api_key: str) -> object:
    """拒绝一个确认单：不执行，只标记为 rejected 并写审计。"""
    req = confirmation.get_request(confirmation_id)
    if req is None:
        raise HTTPException(status_code=404, detail=f"确认单 #{confirmation_id} 不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"确认单 #{confirmation_id} 当前状态是 {req.status}")

    confirmation.mark_status(confirmation_id, "rejected", api_key)
    log_operation(api_key, role, req.tool_name, json.loads(req.args_json), "rejected",
                  confirmation_id=confirmation_id,
                  result_summary=f"确认单 #{confirmation_id} 被拒绝，未执行")
    return confirmation.get_request(confirmation_id)


def to_openai_schema(tool: ToolMeta) -> dict:
    """把工具转成 OpenAI 函数调用（function calling）需要的 schema。

    模型不是靠看 Python 代码理解工具的，它只能读这段 JSON 描述。
    所以 description 写得好不好，直接决定模型选得对不对。
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            # 直接用 Pydantic 模型的 JSON Schema，自动包含字段类型/枚举/约束
            "parameters": tool.arg_model.model_json_schema(),
        },
    }


def format_status_cn(status: str) -> str:
    """订单状态英文转中文，方便 mock 回答和 observation 阅读。"""
    return ORDER_STATUS_CN.get(status, status)

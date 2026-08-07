"""
schemas.py —— Pydantic DTO（接口数据模型）和工具参数校验模型

职责分两部分，都是"数据契约"：
1. 工具参数校验模型（QueryOrdersArgs 等）：Agent 想调用工具时，参数先经过这些模型校验，
   不合法直接拒绝，不让脏数据碰到数据库。这部分是本模块"参数校验"能力的核心。
2. 接口请求/响应 DTO（ChatRequest / ChatResponse 等）：定义 HTTP 接口进出数据的形状。

和 models.py（ORM）的区别（初学者必看）：
- schemas.py 里的类只描述"数据长什么样"，不碰数据库，靠 Pydantic 做校验和序列化。
- models.py 里的类直接对应数据库表，靠 SQLAlchemy 做增删改查。
- 举例：ChatRequest 里的 question 只是接口入参；而 Order 的每一列才是要存进库的东西。
"""

from typing import Literal

from pydantic import BaseModel, Field

# 说明：订单状态的枚举值写在各个 Args 模型的 Literal 里（和 models.py 的
# ORDER_STATUSES 保持一致）。这样"模型选出来的状态"从源头就是合法值。

# ---------- 工具参数校验模型（每个工具一个） ----------
# 这里的字段就是 Agent 需要从用户问题里解析出来、并由模型生成的参数。
# 所有字段都声明了类型和约束，Pydantic 会自动完成"类型不对/超出范围"的校验。


class QueryCustomersArgs(BaseModel):
    """query_customers 工具的入参：按条件过滤客户。"""

    city: str | None = None          # 按城市过滤，不传就是全部
    tier: Literal["vip", "normal"] | None = None   # 按等级过滤，Literal 限定只能是这两个值之一
    keyword: str | None = None       # 按姓名关键词模糊搜索


class QueryOrdersArgs(BaseModel):
    """query_orders 工具的入参：按条件过滤订单。"""

    status: Literal["pending", "paid", "shipped", "completed", "cancelled"] | None = None
    customer_id: int | None = Field(default=None, gt=0)   # gt=0 表示必须大于 0
    min_amount: float | None = Field(default=None, gt=0)  # 只看金额不低于这个值的订单


class QueryStatsArgs(BaseModel):
    """query_order_stats 工具的入参：按哪个维度做统计。"""

    group_by: Literal["status", "city"] = "status"  # 按状态统计 或 按城市统计


class RunSqlArgs(BaseModel):
    """run_sql_readonly 工具的入参：一段用户想执行的只读 SQL。

    注意：这是"模型生成的 SQL"，绝对不能直接执行！必须先经过 sql_safety.py
    的严格校验，只放行只读查询，再执行。
    """

    sql: str = Field(min_length=5)  # 至少要有点内容，不然没有意义


class CreateOrderArgs(BaseModel):
    """create_order 写入工具的入参：要新增一条订单。"""

    customer_id: int = Field(gt=0)                      # 下单客户（必须存在，handler 里再查）
    product_name: str = Field(min_length=1)             # 商品名不能是空字符串
    amount: float = Field(gt=0)                         # 金额必须大于 0


class UpdateOrderStatusArgs(BaseModel):
    """update_order_status 写入工具的入参：把某订单改成某个状态。"""

    order_id: int = Field(gt=0)
    new_status: Literal["pending", "paid", "shipped", "completed", "cancelled"]


class DeleteOrderArgs(BaseModel):
    """delete_order 写入工具的入参：删除某订单。"""

    order_id: int = Field(gt=0)


# ---------- Agent 决策模型 ----------


class ToolDecision(BaseModel):
    """Agent 的一次决策：选哪个工具 + 传什么参数。

    tool_name 是工具名；args 是给该工具的参数（工具注册表里有校验模型，
    执行时会再用 Pydantic 校验一遍，防止模型生成非法参数）。
    """

    tool_name: str
    args: dict


# ---------- HTTP 接口 DTO ----------


class ChatRequest(BaseModel):
    """/agent/chat 的请求体：用户对数据库助手说的一句话。"""

    question: str = Field(min_length=1, max_length=500)


class StepOut(BaseModel):
    """Agent 执行过程中的一步，返回给前端展示。"""

    step: str                       # tool_call / observation
    tool_name: str | None = None
    args: dict | None = None
    content: str | None = None      # observation 的内容


class ChatResponse(BaseModel):
    """/agent/chat 的响应体。

    相比普通聊天接口，多返回了 steps（中间过程）和 confirmation_id（写操作确认单）。
    """

    question: str
    answer: str
    steps: list[StepOut]
    role: str                       # 当前请求的身份角色
    confirmation_id: int | None = None  # 如果触发了写操作，这里给出确认单 id


class ToolRunRequest(BaseModel):
    """/tool/run 的请求体：手动调用某个工具。"""

    tool_name: str
    args: dict = Field(default_factory=dict)


class ToolRunResponse(BaseModel):
    """/tool/run 的响应体。status 解释：
    success 已执行成功；awaiting_confirmation 写操作等待确认；
    blocked 权限不足；failed 执行失败（校验/业务规则/异常）。
    """

    status: str
    message: str
    data: dict | None = None
    confirmation_id: int | None = None


class ToolInfo(BaseModel):
    """/tools 里返回的单个工具信息。"""

    name: str
    description: str
    min_role: str          # 最低需要什么角色
    risk: str              # 风险等级 low/medium/high
    is_write: bool         # 是否写操作
    requires_confirmation: bool  # 是否需要人工确认


class ConfirmationOut(BaseModel):
    """确认单的展示 DTO（不能把 ORM 对象直接返回给前端）。"""

    id: int
    tool_name: str
    args: dict
    requested_by: str
    requested_role: str
    status: str
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    result_summary: str | None = None
    error: str | None = None


class AuditLogOut(BaseModel):
    """审计日志的展示 DTO。"""

    id: int
    op_time: str
    api_key: str
    role: str
    tool_name: str
    args: dict
    sql_text: str | None = None
    row_count: int | None = None
    status: str
    confirmation_id: int | None = None
    result_summary: str | None = None
    error: str | None = None


def serialize_confirmation(req) -> ConfirmationOut:
    """把 ConfirmationRequest 的 ORM 对象转成 DTO。

    为什么不能直接返回 ORM 对象？
    1. ORM 对象里有数据库时间对象 datetime，JSON 序列化会失败。
    2. 直接暴露 ORM 对象，等于把表结构透传给前端，不安全也不优雅。
    这个"ORM -> DTO"的转换是真实项目里非常常见的一步。
    """
    return ConfirmationOut(
        id=req.id,
        tool_name=req.tool_name,
        args=_parse_json(req.args_json),
        requested_by=req.requested_by,
        requested_role=req.requested_role,
        status=req.status,
        created_at=req.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        decided_at=req.decided_at.strftime("%Y-%m-%d %H:%M:%S") if req.decided_at else None,
        decided_by=req.decided_by,
        result_summary=req.result_summary,
        error=req.error,
    )


def serialize_audit_log(log) -> AuditLogOut:
    """把 DatabaseOpLog 的 ORM 对象转成 DTO，道理同上。"""
    return AuditLogOut(
        id=log.id,
        op_time=log.op_time.strftime("%Y-%m-%d %H:%M:%S"),
        api_key=log.api_key,
        role=log.role,
        tool_name=log.tool_name,
        args=_parse_json(log.args_json),
        sql_text=log.sql_text,
        row_count=log.row_count,
        status=log.status,
        confirmation_id=log.confirmation_id,
        result_summary=log.result_summary,
        error=log.error,
    )


def _parse_json(s: str | None) -> dict:
    """把存成 JSON 字符串的参数解析回 dict，解析失败返回空字典（容错）。"""
    import json

    if not s:
        return {}
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return {}

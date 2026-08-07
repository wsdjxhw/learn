"""
models.py —— ORM 模型（数据库表）

职责：用 Python 类描述 4 张表的结构。ORM 类 ≈ Java 里的 Entity 类：
一个类对应一张表，一个对象对应一行数据，一个属性对应一列。

初学者最容易搞混的概念（重要！）：
- ORM Model（本文件）：直接对应数据库表，负责"读写数据库"。
- Pydantic DTO（schemas.py）：只负责"接口进出参数"，和数据库无关。
  真实项目里这两类必须分开，因为：
    1. 数据库字段通常比接口字段多（比如 created_at 不该让用户随便传）。
    2. 接口返回什么由前端决定，数据库存什么由表结构决定，两者不是一回事。
    3. 写数据库的模型不该直接暴露给用户（用户可能塞一个你不知道的字段）。

本模块的 4 张表：
1. customers          —— 业务数据：客户
2. orders             —— 业务数据：订单（本模块 Agent 主要操作的对象）
3. confirmation_requests —— 写操作确认单（写数据库前的"人工确认"门）
4. database_op_logs   —— 审计日志（每一次数据库操作都记录，可追溯）
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# 订单状态枚举。真实项目里一般会做成一张配置表或数据库枚举，
# 教学版为了让大家一眼看懂，用 Python 常量 + 注释说明。
ORDER_STATUSES = ["pending", "paid", "shipped", "completed", "cancelled"]
# 各状态的中文含义，方便理解 demo 数据
ORDER_STATUS_CN = {
    "pending": "待付款",
    "paid": "已付款",
    "shipped": "已发货",
    "completed": "已完成",
    "cancelled": "已取消",
}


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。

    它做的事情是：收集所有继承它的子类，集中管理表和元数据。
    数据库建表（database.py 里的 create_all）就是通过 Base.metadata 拿到全部表的。
    """


class Customer(Base):
    """客户表。业务数据：谁在买。"""

    __tablename__ = "customers"

    # Mapped[int] 是 SQLAlchemy 2.0 的写法：表示 id 列是 int 类型。
    # mapped_column(...) 才真正定义这一列的各种属性。
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))   # 客户姓名
    city: Mapped[str] = mapped_column(String(50))   # 所在城市，方便按城市统计
    tier: Mapped[str] = mapped_column(String(10), default="normal")  # 客户等级 vip/normal
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # relationship 只在 ORM 层建立"关联"，不会真的在数据库里生成外键列。
    # 作用是让我们能通过 customer.orders 拿到这个客户的订单列表（本模块很少用，属进阶）。
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    """订单表。业务数据：买了什么、多少钱、什么状态。

    这是本模块 Agent 的核心操作对象。
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))  # 外键：属于哪个客户
    product_name: Mapped[str] = mapped_column(String(100))  # 商品名
    amount: Mapped[float] = mapped_column(Float)  # 金额

    # 教学版为了简单用 Float 存金额。真实项目里钱必须用 Numeric(10,2)/Decimal，
    # 因为浮点数有精度问题（比如 0.1 + 0.2 != 0.3），涉及钱一定会出 bug。
    status: Mapped[str] = mapped_column(String(20), default="pending")  # 订单状态
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class ConfirmationRequest(Base):
    """写操作确认单。

    作用：当 Agent 想执行"写数据库"操作（创建订单/改状态/删订单）时，
    并不会直接执行，而是先创建一条 pending 状态的确认单，保存当时想要执行
    的工具名和参数快照。用户（或审批人）明确 approve 之后才真正执行。

    这就像一个"待办审批单"：先把"我要做什么"写下来，等人盖章。
    """

    __tablename__ = "confirmation_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tool_name: Mapped[str] = mapped_column(String(50))   # 想执行哪个写工具，如 update_order_status
    args_json: Mapped[str] = mapped_column(Text)         # 参数快照（JSON 字符串），审批时按这份参数执行
    requested_by: Mapped[str] = mapped_column(String(50))  # 谁发起的（API Key）
    requested_role: Mapped[str] = mapped_column(String(20))  # 发起人角色
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/executed/rejected/failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 审批时间
    decided_by: Mapped[str | None] = mapped_column(String(50), nullable=True)     # 审批人
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)       # 执行结果摘要
    error: Mapped[str | None] = mapped_column(Text, nullable=True)                # 执行失败原因


class DatabaseOpLog(Base):
    """审计日志表。

    记录每一次"对数据库的操作尝试"，注意是"尝试"：
    成功的、被权限拦下的、参数校验失败的、被人工拒绝的，全部都要记。
    为什么连失败的也要记？因为安全审计要回答的问题不是"谁成功了"，
    而是"谁在什么时间，对哪张表，想干什么"。只有记录所有尝试，
    才能真正排查越权、误操作和恶意行为。
    """

    __tablename__ = "database_op_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    op_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    api_key: Mapped[str] = mapped_column(String(50))     # 谁发起（API Key）
    role: Mapped[str] = mapped_column(String(20))        # 发起人角色
    tool_name: Mapped[str] = mapped_column(String(50))   # 哪个工具
    args_json: Mapped[str] = mapped_column(Text)         # 参数 JSON
    sql_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # 最终生成的 SQL（教学亮点）
    row_count: Mapped[int | None] = mapped_column(nullable=True)       # 影响/返回行数
    status: Mapped[str] = mapped_column(String(20))  # requested/executed/rejected/blocked/failed
    confirmation_id: Mapped[int | None] = mapped_column(nullable=True)  # 关联的确认单（写操作才有）
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # 结果摘要
    error: Mapped[str | None] = mapped_column(Text, nullable=True)       # 错误详情

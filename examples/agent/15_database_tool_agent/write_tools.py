"""
write_tools.py —— 写入工具（创建/修改/删除订单）

这三个工具是"高危"的：它们会真正改动数据库。所以：
1. 它们必须通过 tool_registry 的"人工确认门"：Agent 想执行 -> 先建确认单 ->
   审批人 approve 后才会真正调用这里的 handler。
2. handler 内部还要做"业务规则校验"（不只是类型校验）。

业务规则校验和类型校验的区别（重要）：
- 类型/枚举校验（schemas.py 的 Pydantic）："status 必须是五个状态之一"，是硬约束。
- 业务规则校验（本文件抛 BusinessRuleError）："已付款的订单不能删"，
  这是业务常识，不是类型问题。真实项目里这两层都存在，缺一不可。
"""

from errors import BusinessRuleError
from database import SessionLocal
from models import Customer, Order
from sqlalchemy import select

# 订单状态机：记录每个状态可以"变成"哪些状态。
# 例如 pending 只能变成 paid 或 cancelled，不能直接跳成 completed。
# 为什么要有状态机？因为业务上订单的流转是严格有序的：
# 不可能"还没发货就完成"，也不可能"已完成又变回待付款"。
ALLOWED_TRANSITIONS = {
    "pending": ["paid", "cancelled"],
    "paid": ["shipped", "cancelled"],
    "shipped": ["completed"],
    "completed": [],
    "cancelled": [],
}

# 不允许删除的订单状态：防止误删还在履约中的订单。
# 规则：只有待付款、已取消的订单可以删；已付款/已发货/已完成的必须先取消。
UNSAFE_TO_DELETE = {"paid", "shipped", "completed"}


def handle_create_order(args, role: str) -> dict:
    """创建一条新订单（初始状态 pending）。"""
    with SessionLocal() as db:
        # 第一步：业务校验 —— 客户必须真实存在（外键约束之外的人工检查）
        customer = db.get(Customer, args.customer_id)
        if customer is None:
            raise BusinessRuleError(f"客户 #{args.customer_id} 不存在，无法下单")

        # 第二步：真正写入（INSERT）
        order = Order(
            customer_id=args.customer_id,
            product_name=args.product_name,
            amount=args.amount,
            status="pending",
        )
        db.add(order)
        db.commit()
        db.refresh(order)  # 刷新拿到自增 id
        return {"order_id": order.id, "message": f"订单 #{order.id} 创建成功，状态为待付款"}


def handle_update_order_status(args, role: str) -> dict:
    """修改订单状态，带状态机校验。"""
    with SessionLocal() as db:
        order = db.get(Order, args.order_id)
        if order is None:
            raise BusinessRuleError(f"订单 #{args.order_id} 不存在")

        current = order.status
        new = args.new_status

        # 状态机校验：当前状态能不能变成目标状态？
        if new not in ALLOWED_TRANSITIONS.get(current, []):
            raise BusinessRuleError(
                f"订单 #{order.id} 当前状态是 {current}，不能直接改为 {new}。"
                f"允许的流转：{ALLOWED_TRANSITIONS.get(current, [])}"
            )

        # 如果目标状态和当前一样，属于无意义操作，提前拦截
        if new == current:
            raise BusinessRuleError(f"订单 #{order.id} 已经是 {current} 状态，无需修改")

        # 真正执行 UPDATE
        order.status = new
        db.commit()
        db.refresh(order)
        return {"order_id": order.id, "new_status": new, "message": f"订单 #{order.id} 状态已更新为 {new}"}


def handle_delete_order(args, role: str) -> dict:
    """删除订单，带"不能删履约中订单"的业务校验。"""
    with SessionLocal() as db:
        order = db.get(Order, args.order_id)
        if order is None:
            raise BusinessRuleError(f"订单 #{args.order_id} 不存在")

        if order.status in UNSAFE_TO_DELETE:
            raise BusinessRuleError(
                f"订单 #{order.id} 状态是 {order.status}，属于履约中订单，不能删除。"
                "请先把状态改为 cancelled（待付款/已取消的订单才允许删除）"
            )

        # 真正执行 DELETE。注意 delete 之后对象就失效了，所以要提前记住 id
        order_id = order.id
        db.delete(order)
        db.commit()
        return {"order_id": order_id, "message": f"订单 #{order_id} 已删除"}

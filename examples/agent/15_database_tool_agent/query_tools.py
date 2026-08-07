"""
query_tools.py —— 查询工具（只读，不碰数据库的写操作）

职责：把"查客户 / 查订单 / 查统计"封装成 Agent 可以主动调用的工具。
每个函数对应一个工具，输入是 Pydantic 校验过的参数，输出是一个 dict。

为什么查询工具的输出是一个 dict 而不是直接返回给前端？
- 这个 dict 是"工具执行结果"，后面还有 Agent 要把结果转成自然语言回答，
  还要把结果压缩成 observation 塞给模型。先用统一结构，方便复用。

为什么查询工具里生成的 SQL 也要返回？
- 因为审计日志要记录"这次查询最终执行了什么 SQL"（sql_text 列）。
  真实项目里看到"Agent 的意图变成了什么 SQL"是排查问题的重要线索。
"""

from sqlalchemy import func, select

from database import SessionLocal
from models import Customer, Order


def handle_query_customers(args, role: str) -> dict:
    """按条件查客户。args 是 Pydantic 校验过的 QueryCustomersArgs。"""
    with SessionLocal() as db:
        stmt = select(Customer).order_by(Customer.id)
        if args.city:          # 注意：这里每个条件都是"可选拼接"，不传就不加这个过滤
            stmt = stmt.where(Customer.city == args.city)
        if args.tier:
            stmt = stmt.where(Customer.tier == args.tier)
        if args.keyword:
            # like 做模糊匹配，% 表示任意字符。contain 也能达到同样效果。
            stmt = stmt.where(Customer.name.like(f"%{args.keyword}%"))

        rows = list(db.scalars(stmt).all())
        return {
            "sql": str(stmt),  # 把生成的 SQL 返回，供审计记录
            "count": len(rows),
            "rows": [
                {"id": c.id, "name": c.name, "city": c.city, "tier": c.tier}
                for c in rows
            ],
        }


def handle_query_orders(args, role: str) -> dict:
    """按条件查订单，并带出客户姓名。

    JOIN 的直观理解：订单表里只存 customer_id 这个外键，看不到客户叫什么。
    想同时拿到客户姓名，就要把 orders 和 customers 两张表按 id 连起来查，
    这就是 JOIN。这里用 SQLAlchemy 的 join 写法，等价于：
        SELECT orders.*, customers.name FROM orders
        JOIN customers ON orders.customer_id = customers.id
    """
    with SessionLocal() as db:
        stmt = (
            select(Order, Customer.name)
            .join(Customer, Order.customer_id == Customer.id)
            .order_by(Order.id)
        )
        if args.status:
            stmt = stmt.where(Order.status == args.status)
        if args.customer_id:
            stmt = stmt.where(Order.customer_id == args.customer_id)
        if args.min_amount is not None:
            stmt = stmt.where(Order.amount >= args.min_amount)

        rows = db.execute(stmt).all()  # 每条记录是 (Order, customer_name) 的元组
        return {
            "sql": str(stmt),
            "count": len(rows),
            "rows": [
                {
                    "order_id": o.id,
                    "customer_name": name,   # JOIN 出来的客户姓名
                    "product_name": o.product_name,
                    "amount": o.amount,
                    "status": o.status,
                }
                for o, name in rows
            ],
        }


def handle_query_stats(args, role: str) -> dict:
    """按状态或按城市统计订单数、订单总金额。

    聚合（GROUP BY）的直观理解：把所有订单按照某个维度（状态/城市）分堆，
    每堆数一下有多少条、金额加起来是多少。func.count / func.sum 就是干这个的。
    """
    with SessionLocal() as db:
        if args.group_by == "status":
            # 按订单状态分组统计
            stmt = (
                select(
                    Order.status,
                    func.count(Order.id).label("order_count"),
                    func.sum(Order.amount).label("total_amount"),
                )
                .group_by(Order.status)
                .order_by(Order.status)
            )
        else:
            # 按客户所在城市分组统计：需要先 JOIN 客户表拿到城市
            stmt = (
                select(
                    Customer.city,
                    func.count(Order.id).label("order_count"),
                    func.sum(Order.amount).label("total_amount"),
                )
                .join(Customer, Order.customer_id == Customer.id)
                .group_by(Customer.city)
                .order_by(Customer.city)
            )

        rows = db.execute(stmt).all()
        group_col = "status" if args.group_by == "status" else "city"
        return {
            "sql": str(stmt),
            "group_by": args.group_by,
            "count": len(rows),
            "rows": [
                {
                    group_col: row[0],
                    "order_count": row[1],
                    # 把可能的 None 转成 0，避免"某状态没有订单"时 sum 返回 None 报错
                    "total_amount": float(row[2]) if row[2] is not None else 0.0,
                }
                for row in rows
            ],
        }

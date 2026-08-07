"""
seed.py —— demo 数据初始化

职责：往数据库里写入一批固定的客户和订单数据，保证每个人跑出来的
演示结果一模一样，方便对照文档学习。

为什么用"固定数据"而不是随机数据？
因为学习时你要能精确复现文档里的查询结果。随机数据会导致
"文档说订单5是已发货，你这边却是别的状态"，无法对照。
"""

from datetime import datetime

from database import SessionLocal, init_db
from models import Customer, Order
from sqlalchemy import func, select

# 固定客户数据
CUSTOMERS = [
    {"name": "张三", "city": "北京", "tier": "vip"},
    {"name": "李四", "city": "上海", "tier": "normal"},
    {"name": "王五", "city": "深圳", "tier": "vip"},
    {"name": "赵六", "city": "北京", "tier": "normal"},
    {"name": "孙七", "city": "广州", "tier": "vip"},
]

# 固定订单数据：customer_id 对应上面客户的下标+1（即客户 id）
ORDERS = [
    {"customer_id": 1, "product_name": "笔记本电脑", "amount": 6800.0, "status": "completed"},
    {"customer_id": 2, "product_name": "键盘",       "amount": 199.0,  "status": "paid"},
    {"customer_id": 3, "product_name": "显示器",     "amount": 1299.0, "status": "shipped"},
    {"customer_id": 4, "product_name": "鼠标",       "amount": 89.0,   "status": "pending"},
    {"customer_id": 1, "product_name": "手机",       "amount": 4299.0, "status": "shipped"},
    {"customer_id": 2, "product_name": "耳机",       "amount": 399.0,  "status": "completed"},
    {"customer_id": 3, "product_name": "显示器",     "amount": 1299.0, "status": "paid"},
    {"customer_id": 4, "product_name": "键盘",       "amount": 199.0,  "status": "cancelled"},
    {"customer_id": 5, "product_name": "笔记本支架", "amount": 159.0,  "status": "pending"},
    {"customer_id": 1, "product_name": "平板电脑",   "amount": 2599.0, "status": "paid"},
]


def seed_if_empty():
    """如果 customers 表是空的，就写入上面的 demo 数据。

    用"空表才写入"而不是"每次启动都写入"，是为了避免你改完数据重启服务后，
    数据又被重置回去，产生"我明明删了订单，重启又出现了"的困惑。
    """
    init_db()  # 先确保表存在
    with SessionLocal() as db:
        # 查一下 customers 表当前有多少行
        count = db.scalar(select(func.count()).select_from(Customer))
        if count and count > 0:
            return  # 已经有数据，不重复写入

        # 批量插入客户，注意要 refresh 拿到自增 id 才能建订单
        customers = []
        for item in CUSTOMERS:
            c = Customer(name=item["name"], city=item["city"], tier=item["tier"])
            db.add(c)
            customers.append(c)
        db.flush()  # 把 add 的语句真正发给数据库，但不提交，此时能拿到自增 id

        # 用刷新出来的客户 id 建立订单（ORDERS 里的 customer_id 就是客户下标+1）
        for item in ORDERS:
            customer_id = item["customer_id"]
            # 校验客户存在，防止 seed 数据写错导致外键失败（防呆检查）
            target = customers[customer_id - 1]
            if target.id != customer_id:
                raise RuntimeError(f"seed 数据客户 id 不匹配: {customer_id}")
            db.add(Order(
                customer_id=target.id,
                product_name=item["product_name"],
                amount=item["amount"],
                status=item["status"],
            ))

        db.commit()  # 一次性提交，要么全部成功，要么全部回滚（事务）
        print("seed 完成：已写入 5 个客户和 10 条订单")

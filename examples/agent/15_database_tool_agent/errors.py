"""
errors.py —— 自定义异常

为什么需要自定义异常？
- 业务规则校验失败（比如"已完成订单不能删除"）不属于程序 bug，也不属于
  权限问题，它有自己的语义。
- 用一个专门的异常类型，能让上层（tool_registry 的执行中枢）统一捕获、
  统一转成用户可读的错误信息，而不是把 Python 底层异常直接抛给前端。
"""


class BusinessRuleError(Exception):
    """业务规则校验失败。

    例如：订单状态不合法、订单不存在、不能删除已付款订单等。
    这类错误是"用户/Agent 的意图不符合业务规则"，可以给用户看原因。
    """


class SqlSafetyError(Exception):
    """SQL 安全校验失败。

    当 run_sql_readonly 发现用户/模型给的 SQL 有风险（例如 DROP TABLE、
    多条语句、访问系统表）时抛出。错误信息会直接告诉用户为什么被拦。
    """

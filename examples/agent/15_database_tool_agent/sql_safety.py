"""
sql_safety.py —— 只读 SQL 安全校验（进阶，但面试必讲）

背景：run_sql_readonly 工具允许用户/模型提交一段 SQL 来查询。
危险在于：这段 SQL 是"模型生成的"，模型完全可能生成破坏性语句，
比如 DROP TABLE、DELETE FROM、甚至访问系统表。所以绝不能直接执行，
必须经过本文件的层层校验，只放行"安全的只读查询"。

这是一个"黑名单 + 白名单"组合的思路：
- 黑名单：禁止的关键字（增删改）、禁止的危险函数、禁止的系统表。
- 白名单：语句必须以 SELECT / WITH 开头，且必须是一条语句。

注意：即使有校验，真实生产环境也绝不给外部用户直接跑任意 SQL。
本工具的定位是"给可信任的内部角色一个灵活的查询入口"，并且
还有权限、限行、只读等兜底。

面试高频点：为什么 LLM 生成的 SQL 不能直接执行？答三层风险——
破坏性（DROP/UPDATE）、越权（访问不该看的表/行）、性能（无 LIMIT 全表扫）。
"""

import re

from errors import SqlSafetyError

# 禁止作为语句开头的关键字：所有"写/破坏"类操作一律拦截
# 注意 re.I 表示忽略大小写，防止模型写小写变体绕过
BLOCKED_PREFIX = re.compile(
    r"^\s*(insert|update|delete|drop|alter|create|truncate|replace|"
    r"pragma|attach|detach|explain|vacuum|reindex|analyze|copy)\b",
    re.I,
)

# SQLite 内置的"写文件/读文件/加载扩展"危险函数
# 如果不禁掉 load_extension，攻击者可能加载任意 C 扩展，直接读写服务器文件
DANGEROUS_FUNCTIONS = ["load_extension", "writefile", "readfile", "dblite"]

# SQLite 系统表：里面存着表结构信息，不该让查询者访问（信息泄露面）
SYSTEM_TABLES = ["sqlite_master", "sqlite_schema", "sqlite_temp_master", "sqlite_sequence", "sqlite_stat"]

# 单次查询最多返回多少行，防止模型生成无 LIMIT 的全表查询打垮数据库
MAX_RESULT_ROWS = 50

# 允许的最多行数上限，超过就重写
HARD_LIMIT = 100


def validate_readonly_sql(raw_sql: str) -> str:
    """对一段 SQL 做只读安全校验，通过后返回可安全执行的 SQL。

    返回值 = 校验通过后的 SQL（可能被补上了 LIMIT）。
    不通过就抛 SqlSafetyError，错误信息会原样展示给用户。
    """
    sql = _strip_comments(raw_sql).strip()

    # 规则1：不能有分号。因为分号是 SQLite 分隔多条语句的标记，
    # 出现分号意味着攻击者想塞多条语句（例如 "SELECT 1; DROP TABLE orders"）。
    if ";" in sql:
        raise SqlSafetyError("检测到多条语句（分号），只允许执行一条只读查询")

    # 规则2：必须以 SELECT 或 WITH（CTE 临时表）开头。
    # 注意用 ^ 锚定开头，防止 "DROP TABLE x" 前面加空格绕过。
    if not re.match(r"^\s*(select|with)\b", sql, re.I):
        raise SqlSafetyError("只允许 SELECT / WITH 开头的只读查询")

    # 规则3：再次检查开头是否为禁止关键字（双保险，因为规则2已排除大部分）
    if BLOCKED_PREFIX.search(sql):
        raise SqlSafetyError("查询包含被禁止的写/破坏操作")

    # 规则4：检查危险函数（load_extension 等）
    lower = sql.lower()
    for fn in DANGEROUS_FUNCTIONS:
        if fn in lower:
            raise SqlSafetyError(f"查询包含危险函数 {fn}，已禁止")

    # 规则5：检查系统表
    for t in SYSTEM_TABLES:
        if t in lower:
            raise SqlSafetyError(f"不允许访问系统表 {t}")

    # 规则6：强制 LIMIT。没有 LIMIT 的查询可能拖垮数据库（性能保护）。
    # 用正则找出已有的 limit，没有就补一个 MAX_RESULT_ROWS。
    limit_match = re.search(r"\blimit\s+(\d+)", sql, re.I)
    if limit_match:
        limit = int(limit_match.group(1))
        if limit > HARD_LIMIT:  # 允许查询但不能太大
            sql = re.sub(r"\blimit\s+\d+", f"LIMIT {HARD_LIMIT}", sql, flags=re.I)
    else:
        sql = f"{sql} LIMIT {MAX_RESULT_ROWS}"

    return sql


def execute_readonly_sql(sql: str, db) -> dict:
    """执行已经过校验的只读 SQL，把结果转成可 JSON 序列化的 dict。

    db 是一个已打开的 SQLAlchemy Session。返回：
      {"count": 行数, "columns": [列名], "rows": [{"列名": 值, ...}, ...]}
    """
    from sqlalchemy import text

    result = db.execute(text(sql))       # text() 把字符串包装成可执行 SQL
    rows = result.fetchall()             # 取出所有行
    columns = list(result.keys())        # 拿到列名

    data_rows = []
    for row in rows[:MAX_RESULT_ROWS]:   # 截断行数，防止内存被撑爆
        # 每行转成 {列名: 值} 的字典，值统一做 JSON 安全转换
        data_rows.append(
            {col: _json_safe(value) for col, value in zip(columns, row)}
        )

    return {"count": len(rows), "columns": columns, "rows": data_rows}


def _strip_comments(sql: str) -> str:
    """去掉 SQL 里的注释（-- 行注释 和 /* */ 块注释）。

    为什么要先剥注释？因为注释可以隐藏攻击内容，例如：
        SELECT 1 -- ; DROP TABLE orders
    如果不去注释，黑名单检测可能被绕过。先剥干净再检查更安全。
    """
    # 去掉 -- 到行尾的内容（注意避开字符串内的 --，教学版简化处理）
    sql = re.sub(r"--[^\n]*", "", sql)
    # 去掉 /* */ 块注释（. 不匹配换行，用 re.S 让 . 匹配换行）
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    return sql


def handle_run_sql_readonly(args, role: str) -> dict:
    """run_sql_readonly 工具的真正处理器。

    args 是 Pydantic 校验过的 RunSqlArgs（含 sql 字段）。
    流程：先过 validate_readonly_sql 安全校验，再执行，再返回可序列化的结果。
    任何一步被拦截都会抛 SqlSafetyError，由 tool_registry 统一转成失败结果。
    """
    from database import SessionLocal  # 局部导入，避免 sql_safety 反向依赖

    # 第一步：安全校验。这一步可能抛 SqlSafetyError（黑名单命中/多语句/无 LIMIT 自动补）
    safe_sql = validate_readonly_sql(args.sql)

    with SessionLocal() as db:
        result = execute_readonly_sql(safe_sql, db)

    # 把校验后的 SQL 一起返回，审计日志能看到"最终执行的到底是什么"
    return {"sql": safe_sql, **result}


def _json_safe(value):
    """把数据库值转成能 JSON 序列化的类型。

    为什么需要这个？SQLite 返回的 datetime 对象直接 json.dumps 会报错，
    返回的 Decimal 也一样。统一转成 str/int/float，保证接口能正常返回。
    """
    if value is None:
        return None
    if isinstance(value, (int, float, bool, str)):
        return value
    # datetime / Decimal 等复杂类型统一转字符串
    return str(value)

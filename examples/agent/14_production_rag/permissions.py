"""
permissions.py - 用户身份与文档级权限

职责：
1. 把“教学 API Key”映射成“用户身份”（user_id + role）。
2. 判断一个用户能不能“看 / 删”某份文档。

⚠️ 重要区分：
模块 10-12 的 permissions.py 管的是“工具权限”（这个用户能不能调某个工具）；
本模块的 permissions.py 管的是“数据权限”（这个用户能看到哪些文档）。
这是两类完全不同的权限，真实项目里通常分别实现、分别校验。

真实项目怎么做的？
- 用户身份来自登录态 / JWT / session，而不是一个写死的 key；
- 文档权限用 RBAC（角色）+ 数据级权限（组织、部门、共享成员表）组合；
- 权限判断发生在 SQL 层（WHERE 条件里过滤），而不是把所有数据捞出来再逐个判断。
  教学版为了讲清楚，先实现成“能看哪些文档的集合”，再从集合里过滤。
"""
from typing import Optional

from fastapi import Header, HTTPException

from models import Document
from settings import settings


class User:
    """一个简化的用户身份对象。

    字段来源：由 API Key 查映射表得到。
    真实项目里这里就是登录后解析出来的用户对象（含 user_id、角色、部门等）。
    """

    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role  # viewer / operator / admin（沿用模块 10 的角色名，含义不同）

    def is_admin(self) -> bool:
        return self.role == "admin"


# API Key -> 用户身份 的映射表（教学用，写死在这里）。
# 真实项目里密钥保存在数据库/密钥服务，并做哈希，绝不存明文。
API_KEY_TO_USER = {
    settings.learner_api_key: User("alice", "viewer"),
    settings.operator_api_key: User("bob", "operator"),
    settings.admin_api_key: User("admin", "admin"),
}


def get_current_user(
    # FastAPI 会从请求头里取 X-API-Key 的值。
    # Header() 里的别名，让代码里用 api_key 变量，而不是写 X-API-Key。
    # 默认 "learner-key"：不传 key 也能跑通（方便初学者先跑 mock）。
    api_key: Optional[str] = Header(default=settings.learner_api_key, alias="X-API-Key"),
) -> User:
    """依赖注入函数：根据请求头里的 API Key，得到当前用户身份。

    用途：给接口函数做参数注入，例如
        def upload(file: UploadFile, user: User = Depends(get_current_user)):
    这样接口里直接用 user.user_id，不用自己解析 key。
    """
    user = API_KEY_TO_USER.get(api_key)
    if user is None:
        # 未知 key 直接拒绝，并给出“怎么算合法 key”的提示，方便初学者排查。
        raise HTTPException(
            status_code=401,
            detail=f"未知的 API Key。合法 key：{settings.learner_api_key} / {settings.operator_api_key} / {settings.admin_api_key}",
        )
    return user


def can_view_document(user: User, doc: Document) -> bool:
    """判断一个用户能不能看这份文档（文档级权限的核心判断）。

    规则（教学版简化成两级可见范围）：
    1. admin 能看所有文档；
    2. 文档是 public -> 所有用户都能看；
    3. 文档是 private -> 只有 owner 自己能看。

    真实项目里这里通常还要查：
    - 部门 / 组织层级（上级能看到下级的文档吗？）；
    - 文档共享成员表（用户 A 显式把文档分享给了用户 B）；
    - 特殊授权（临时链接 / 过期授权）。
    万变不离其宗：最后都收敛成一个布尔判断“这个用户对这个文档有没有权限”。
    """
    # 文档共享给了哪些用户：逗号分隔的字符串 -> 列表。
    # strip + 过滤空串：避免存成 "alice, bob"（带空格）或 "alice,,bob" 时匹配失败。
    shared_users = [u.strip() for u in doc.shared_with.split(",")] if doc.shared_with else []
    if user.user_id in shared_users:
        return True
    if user.is_admin():
        return True
    if doc.visibility == "public":
        return True
    return doc.owner_id == user.user_id


def can_delete_document(user: User, doc: Document) -> bool:
    """判断一个用户能不能删这份文档。

    删除是写操作，权限比“看”更严：
    只有 owner 自己或 admin 能删。public 不改变删除权限
    —— 别人能看你的公开文档，不代表别人能删你的文档。
    真实项目里写操作权限几乎总是比读操作更严格，这是通用原则。
    """
    if user.is_admin():
        return True
    return doc.owner_id == user.user_id

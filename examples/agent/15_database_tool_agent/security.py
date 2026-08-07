"""
security.py —— API Key 鉴权和角色权限

职责：
1. 把请求头 X-API-Key 映射成角色（viewer / operator / admin）。
2. 提供角色等级比较函数，判断"某个角色能不能干这件事"。

为什么要有角色？
数据库智能体最大的风险是"模型替用户乱改数据"。所以读和写必须分开：
- viewer（只读）：只能查，永远碰不了数据库的写操作。
- operator（操作员）：可以发起写操作，但必须走人工确认，且能审批。
- admin（管理员）：本模块里与 operator 权限相同，统一保留确认环节
  （真实项目里 admin 可能可以跳过确认，这里为了演示安全边界故意统一）。

API Key 是什么？
它就是一个"钥匙串"，前端/调用方把它放在请求头里发过来，
后端靠它识别"你是谁"。真实项目里会用 JWT 登录、OAuth、session 等，
但核心思想一样：给每个请求一个可识别的身份。
"""

from dataclasses import dataclass

from fastapi import Header, HTTPException

from settings import settings

# 角色等级：数字越大权限越高。用数字是为了方便做"最低等级"判断。
ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}

# API Key -> 角色 的静态映射表，从配置里读取。
# 教学版用固定 Key 映射角色；真实项目里 Key 存在用户表里，可以动态增删。
API_KEY_ROLE = {
    settings.viewer_api_key: "viewer",
    settings.operator_api_key: "operator",
    settings.admin_api_key: "admin",
}


@dataclass
class UserContext:
    """当前请求的身份上下文，往后传的参数包。"""

    api_key: str
    role: str


def role_for_key(api_key: str) -> str | None:
    """根据 API Key 返回角色，不认识就返回 None。"""
    return API_KEY_ROLE.get(api_key)


def has_role(min_role: str, actual_role: str) -> bool:
    """判断 actual_role 是否达到 min_role 的要求。

    例如：has_role("operator", "admin") -> True，admin 当然能干活 operator 的活；
          has_role("operator", "viewer") -> False。
    """
    return ROLE_LEVEL.get(actual_role, 0) >= ROLE_LEVEL.get(min_role, 99)


def get_current_user(x_api_key: str = Header(default="")) -> UserContext:
    """FastAPI 依赖注入：从请求头解析出当前用户身份。

    参数来源说明（初学者必看）：
    接口函数里的参数 x_api_key 虽然类型是 str，但 FastAPI 不会把它当普通参数——
    它会根据参数名和类型去请求头里找名为 X-API-Key 的值。这就是
    "参数从哪来"：路径参数从 URL 来，Query 从 ? 来，Body 从请求体来，
    Header 从请求头来，Depends 从依赖注入来。
    """
    role = role_for_key(x_api_key)
    if role is None:
        # 没有有效的 Key，直接返回 401 未授权
        raise HTTPException(status_code=401, detail="无效的 API Key，请检查请求头 X-API-Key")
    return UserContext(api_key=x_api_key, role=role)

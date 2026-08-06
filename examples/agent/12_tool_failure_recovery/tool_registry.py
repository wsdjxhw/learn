from dataclasses import dataclass
from typing import Any

from schemas import RiskLevel, ToolType, UserRole


@dataclass(frozen=True)
class ToolDefinition:
    # ToolDefinition 是工具注册表里的元数据。
    # 它不执行工具，只描述工具：叫什么、能做什么、属于读还是写、需要什么角色。
    # Java 类比：像一个工具配置类或枚举配置，而不是具体 Service 实现。
    name: str
    description: str
    tool_type: ToolType
    risk_level: RiskLevel
    allowed_roles: tuple[UserRole, ...]
    requires_confirmation: bool = False
    timeout_seconds: float = 2.0
    max_retries: int = 0
    fallback_tool_name: str | None = None
    expose_to_model: bool = True
    enabled: bool = True

    def to_openai_tool_schema(self) -> dict[str, Any]:
        # 这个 schema 会传给 OpenAI 兼容的模型接口。
        # 注意 schema 只是告诉模型“有哪些工具可以选”，真正的权限检查必须仍然由后端执行。
        parameters = TOOL_PARAMETERS[self.name]
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "get_user_plan": {
        "type": "object",
        "properties": {
            "target_user_id": {
                "type": "string",
                "description": "要查看哪个用户的套餐。普通操作员只能查看自己。",
            }
        },
        "required": ["target_user_id"],
    },
    "search_company_policy": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "要检索的制度关键词，例如：报销、假期、密码、退款。",
            }
        },
        "required": ["keyword"],
    },
    "get_memory_summary": {
        "type": "object",
        "properties": {
            "target_user_id": {
                "type": "string",
                "description": "要查看哪个用户的记忆摘要。普通操作员只能查看自己。",
            },
            "topic": {
                "type": "string",
                "description": "记忆主题，例如：偏好、画像、限制。",
            },
        },
        "required": ["target_user_id", "topic"],
    },
    "create_support_ticket": {
        "type": "object",
        "properties": {
            "target_user_id": {
                "type": "string",
                "description": "要为哪个用户创建工单。",
            },
            "title": {
                "type": "string",
                "description": "工单标题。",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high"],
                "description": "工单优先级。",
            },
            "simulate_failure": {
                "type": "string",
                "enum": ["none", "timeout", "transient", "permanent"],
                "description": "教学用故障模拟：none 正常；timeout 超时；transient 短暂失败；permanent 永久失败。",
            },
            "fail_times": {
                "type": "integer",
                "description": "教学用：transient 模式下前几次失败。",
            },
            "requested_delay_seconds": {
                "type": "number",
                "description": "教学用：模拟工具预计耗时，超过 timeout_seconds 会被执行器判定为超时。",
            },
        },
        "required": ["target_user_id", "title"],
    },
    "create_support_ticket_fallback": {
        "type": "object",
        "properties": {
            "target_user_id": {
                "type": "string",
                "description": "要为哪个用户记录降级工单。",
            },
            "title": {
                "type": "string",
                "description": "工单标题。",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high"],
                "description": "工单优先级。",
            },
            "original_error": {
                "type": "string",
                "description": "主工具失败原因。",
            },
        },
        "required": ["target_user_id", "title", "original_error"],
    },
    "update_user_plan": {
        "type": "object",
        "properties": {
            "target_user_id": {
                "type": "string",
                "description": "要修改套餐的用户。",
            },
            "new_plan": {
                "type": "string",
                "enum": ["free", "pro", "enterprise"],
                "description": "新的套餐名称。",
            },
            "reason": {
                "type": "string",
                "description": "修改原因。",
            },
        },
        "required": ["target_user_id", "new_plan", "reason"],
    },
    "list_audit_logs": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "最多返回多少条审计日志。",
            }
        },
        "required": [],
    },
}


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "get_user_plan": ToolDefinition(
        name="get_user_plan",
        description="查看用户套餐。属于中风险读工具，涉及资源归属判断，普通操作员只能查看自己的套餐。",
        tool_type="read",
        risk_level="medium",
        allowed_roles=("viewer", "operator", "admin"),
    ),
    "search_company_policy": ToolDefinition(
        name="search_company_policy",
        description="检索公司制度片段。属于低风险读工具，适合回答报销、假期、密码、退款等制度问题。",
        tool_type="read",
        risk_level="low",
        allowed_roles=("viewer", "operator", "admin"),
    ),
    "get_memory_summary": ToolDefinition(
        name="get_memory_summary",
        description="查看用户长期记忆摘要。属于中风险读工具，因为它可能暴露用户画像或偏好。",
        tool_type="read",
        risk_level="medium",
        allowed_roles=("operator", "admin"),
    ),
    "create_support_ticket": ToolDefinition(
        name="create_support_ticket",
        description="创建客服工单。属于中风险写工具，本模块会演示超时、重试和降级。",
        tool_type="write",
        risk_level="medium",
        allowed_roles=("operator", "admin"),
        timeout_seconds=1.0,
        max_retries=2,
        fallback_tool_name="create_support_ticket_fallback",
    ),
    "create_support_ticket_fallback": ToolDefinition(
        name="create_support_ticket_fallback",
        description="主工单系统失败时，把请求写入教学版降级队列。它是内部降级工具，不暴露给模型主动选择。",
        tool_type="write",
        risk_level="medium",
        allowed_roles=("operator", "admin"),
        timeout_seconds=1.0,
        max_retries=0,
        expose_to_model=False,
    ),
    "update_user_plan": ToolDefinition(
        name="update_user_plan",
        description="修改用户套餐。属于高风险写工具，只有管理员可以发起，并且必须人工确认后才执行。",
        tool_type="write",
        risk_level="high",
        allowed_roles=("admin",),
        requires_confirmation=True,
    ),
    "list_audit_logs": ToolDefinition(
        name="list_audit_logs",
        description="查看工具调用审计日志。属于管理员工具。",
        tool_type="admin",
        risk_level="high",
        allowed_roles=("admin",),
    ),
}


def get_tool_definition(tool_name: str) -> ToolDefinition | None:
    # 统一从注册表拿工具定义，避免工具散落在多个 if/else 里。
    return TOOL_REGISTRY.get(tool_name)


def list_tool_definitions() -> list[ToolDefinition]:
    # 返回所有注册工具。
    # 权限过滤不要写在这里，因为不同场景可能需要“看全部工具”或“只看自己能用的工具”。
    return list(TOOL_REGISTRY.values())

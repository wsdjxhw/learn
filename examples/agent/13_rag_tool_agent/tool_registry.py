from dataclasses import dataclass
from typing import Any

from schemas import RiskLevel, ToolType, UserRole


@dataclass(frozen=True)
class ToolDefinition:
    # ToolDefinition 是工具注册表里的元数据。
    # 它不执行工具，只描述工具：叫什么、能做什么、属于读还是写、需要什么角色。
    # Java 类比：像一个工具配置类，而不是具体 Service 实现。
    #
    # 对比模块 12：本模块只有读工具，所以不需要 timeout_seconds / max_retries /
    # fallback_tool_name / requires_confirmation 这些失败恢复和确认字段。
    # 它们不是被删掉了，而是本模块核心不在这，学完模块 12 后再回来复用即可。
    name: str
    description: str
    tool_type: ToolType
    risk_level: RiskLevel
    allowed_roles: tuple[UserRole, ...]
    expose_to_model: bool = True
    enabled: bool = True

    def to_openai_tool_schema(self) -> dict[str, Any]:
        # 这个 schema 会传给 OpenAI 兼容的模型接口，告诉模型“有哪些工具可以选、参数长什么样”。
        # 注意 schema 只是给模型看的说明，真正的权限检查必须仍然由后端执行。
        parameters = TOOL_PARAMETERS[self.name]
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


# TOOL_PARAMETERS 描述每个工具的参数结构，格式遵循 OpenAI function calling 的规范。
TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "search_documents": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要检索的关键词或自然语言问题，例如：报销流程、请假需要几天审批。",
            },
            "top_k": {
                "type": "integer",
                "description": "最多返回几个相关片段，默认 3。",
            },
        },
        "required": ["query"],
    },
}


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "search_documents": ToolDefinition(
        name="search_documents",
        description="检索企业知识库，返回与 query 最相关的文档片段（sources）。适合回答报销、请假、考勤、制度、流程等知识性问题。",
        tool_type="read",
        risk_level="low",
        allowed_roles=("viewer", "operator", "admin"),
    ),
}


def get_tool_definition(tool_name: str) -> ToolDefinition | None:
    # 统一从注册表拿工具定义，避免工具散落在多个 if/else 里。
    return TOOL_REGISTRY.get(tool_name)


def list_tool_definitions() -> list[ToolDefinition]:
    # 返回所有注册工具。
    return list(TOOL_REGISTRY.values())

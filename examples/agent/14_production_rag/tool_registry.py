"""
tool_registry.py - 工具注册表（本模块的简化版）

职责：集中声明 Agent 能用哪些工具，以及每个工具的参数契约（schema）。

为什么必须有注册表？
1. 白名单：后端只认注册表里声明过的工具。模型想调别的？没有这个工具，调用即失败。
   真实项目里“模型能看到的工具”和“后端允许执行的工具”永远以注册表为准。
2. 参数契约：工具参数要什么、类型是什么、哪些必填，都写清楚，
   模型（function calling）按这个 schema 填参数，后端按这个 schema 校验参数。
3. 展示：/tools 接口和 /agent/chat 里的决策层，都从这里拿工具列表。

和模块 10-12 的区别：
那里有完整的权限、风险等级、审计；本模块是 RAG 专项，
刻意保留“最小可用”的注册表，把注意力放在 RAG 本身。
"""
from typing import Any


def _search_documents_schema() -> dict:
    """search_documents 工具的参数 schema。

    格式遵循 OpenAI function calling 的 parameters 规范：
    type=object 表示参数是一个对象；properties 描述每个参数；
    required 列出必填参数。DeepSeek 走 OpenAI 兼容协议，所以用同一套格式。
    """
    return {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索词，通常是用户问题的关键词，例如'报销流程'",
            },
            "category": {
                "type": "string",
                "description": "文档分类过滤，例如 财务 / 人事 / 产品，不传则不过滤",
            },
            "tags": {
                "type": "string",
                "description": "标签过滤，逗号分隔，例如 '报销,流程'，不传则不过滤",
            },
            "top_n": {
                "type": "integer",
                "description": "最终返回的片段数，默认 3",
            },
        },
        "required": ["query"],
    }


# 注册表主体：工具名 -> 工具的完整定义。
# 类比 Java：一个 Map<String, ToolDefinition>，就是“这个后端认哪些工具”的清单。
TOOLS: dict[str, dict[str, Any]] = {
    "search_documents": {
        "name": "search_documents",
        "description": (
            "在企业知识库中检索文档片段。"
            "检索会按当前用户的权限过滤，并支持按文档分类和标签过滤。"
            "返回的每条结果包含来源文档标题和片段内容。"
        ),
        "parameters": _search_documents_schema(),
    },
}


def get_tools() -> list[dict[str, Any]]:
    """返回工具列表（给模型 function calling 和 /tools 接口用）。"""
    return list(TOOLS.values())


def get_tool(name: str) -> dict[str, Any] | None:
    """按名字取工具定义；不存在返回 None。"""
    return TOOLS.get(name)

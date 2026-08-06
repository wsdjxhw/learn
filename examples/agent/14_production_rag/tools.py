"""
tools.py - 工具执行层

职责：真正执行“search_documents 这个工具到底做了什么”。
     注册表（tool_registry）负责“声明工具”，这里负责“执行工具”。

为什么把“声明”和“执行”分开？
- 声明（schema）是给模型看的：告诉它这个工具怎么用；
- 执行（代码）是给后端做的：真正查库、过滤权限、返回结果；
- 分开之后，模型永远无法“绕过”执行逻辑直接拿数据，
  它只能填参数，剩下的权限校验、范围控制都由执行层兜底。
  这就是“工具调用的后端兜底”在真实项目里的样子。

本模块的工具就是 RAG 检索。执行时：
1. 校验参数（模型可能填错，后端必须再查一遍）；
2. 带上当前用户身份去检索（权限过滤在这里生效）；
3. 返回带 sources 的结构化结果。
"""
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from permissions import User
from rag import run_rag_search
from settings import settings
from tool_registry import get_tool


def execute_search_documents(
    db: Session,
    user: User,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """执行 search_documents 工具。

    参数：
        db: 数据库会话。
        user: 当前用户（执行工具的人，决定能看到哪些文档）。
        arguments: 模型填的工具参数，例如 {"query": "报销流程", "top_n": 3}。
                   这个参数来自 function calling 返回的 tool_calls，
                   也可能来自 /tool/run 手动测试时前端填的表单。

    返回：
        给模型看 / 给前端展示的结果 dict：
        {
          "sources": [...],       # 检索到的片段（带文档标题）
          "note": "共检索到 N 条",  # 附带说明
        }
    """
    # ---------- 第一步：参数校验（后端兜底） ----------
    # 模型是概率生成，可能漏参数、填错类型。后端必须当它“完全不可信”。
    # 这里做最基础的检查：query 必须有；top_n 必须是合理数字。
    query = arguments.get("query")
    if not query or not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="search_documents 缺少必填参数 query")
    category = arguments.get("category")
    tags = arguments.get("tags")
    top_n = int(arguments.get("top_n", 3))
    # 限制 top_n 范围，防止模型要求返回 1000 条把上下文塞爆
    if top_n < 1 or top_n > 10:
        raise HTTPException(status_code=400, detail="top_n 必须在 1-10 之间")

    # ---------- 第二步：执行检索（权限过滤在 rag.run_rag_search 内部） ----------
    # min_score：相关性阈值。工具返回给模型的 sources 只保留真正相关的片段，
    # 低分“碰巧命中”的片段会污染模型回答，必须挡掉。
    result = run_rag_search(
        db, user,
        query=query,
        category=category if category else None,
        tags=tags if tags else None,
        top_n=top_n,
        min_score=settings.rag_min_score,
    )

    # ---------- 第三步：组织返回结构 ----------
    return {
        "sources": result.sources,
        "note": (
            f"在 {result.filtered_documents} 篇可见文档中检索到 "
            f"{len(result.sources)} 个相关片段"
        ),
    }

from typing import Any

from sqlalchemy.orm import Session

from rag import search_documents_in_db


def run_tool(
    db: Session,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    # run_tool 是工具执行的统一入口，main.py 和 Agent 都通过它执行工具。
    # 工具本身只做“一件事”：search_documents 就是检索知识库。
    # 权限、审计这些横切逻辑由调用方（main.py）负责，不让工具函数自己掺和。
    if tool_name == "search_documents":
        return _search_documents(db, arguments)

    return {
        "ok": False,
        "tool_name": tool_name,
        "error": f"工具 {tool_name} 未注册或未实现。",
    }


def _search_documents(db: Session, arguments: dict[str, Any]) -> dict[str, Any]:
    # 从模型传过来的参数里取 query 和 top_k。
    # arguments 是 dict，所以这里要做“默认值”处理：模型可能只传了 query，没传 top_k。
    query = str(arguments.get("query", "")).strip()
    if not query:
        # 参数校验：query 是必填的。返回可读错误，而不是让程序抛异常。
        return {
            "ok": False,
            "tool_name": "search_documents",
            "count": 0,
            "results": [],
            "error": "search_documents 缺少必填参数 query。",
        }

    try:
        top_k = int(arguments.get("top_k", 3))
    except (TypeError, ValueError):
        # 模型可能传一个没法转成数字的值，此时回退到默认值，而不是让接口 500。
        top_k = 3
    # top_k 做上限保护，避免模型传一个超大数字拖慢接口。
    top_k = max(1, min(top_k, 5))

    return search_documents_in_db(db=db, query=query, top_k=top_k)

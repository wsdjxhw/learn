"""
eval_runner.py - RAG 评测前置（教学版）

职责：读取 eval_cases.json 里的测试问题集，逐条跑 RAG 检索，
     检查“期望命中的文档”是否真的出现在最终结果里，汇总成召回率。

为什么现在就要做评测？
因为“改了检索 / 切分 / rerank 之后到底变好了没有”，靠感觉说不清。
评测的价值就是给每次改动一个可对比的数字。本模块只做最朴素的 recall@n，
模块 21（Agent 评测）会扩展成更完整的评测体系，这里先把数据格式和运行入口铺好。

教学版评测的两个明显简化：
1. 只用“文档标题是否出现在最终结果里”判断命中，没有判断“命中的片段是否真正回答了问题”；
2. 只在内存里跑一次，没有保存评测历史，无法对比多个版本。
这两点就是真实评测系统要解决的方向，后面模块会补。

⚠️ 一个重要设计：评测必须带上“当前用户”。
因为检索受权限过滤影响：同样的问题，admin 能看到私有文档，bob 看不到。
所以同一个 case 在不同用户下可能得到不同的 recall —— 这不是 bug，
而是提醒你：评测要贴近真实权限环境，否则数字好看但实际不可用。
"""
import json
import os

from sqlalchemy.orm import Session

from permissions import User
from rag import run_rag_search

# 评测数据集路径：和本文件同目录的 eval_cases.json
CASES_PATH = os.path.join(os.path.dirname(__file__), "eval_cases.json")


def _load_cases() -> list[dict]:
    """读取评测数据集。用 utf-8 明确指定编码，避免 Windows 上中文乱码。"""
    with open(CASES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def run_eval(db: Session, user: User, top_n: int = 3) -> dict:
    """对全部评测 case 跑一次检索，返回汇总结果。

    参数：
        db: 数据库会话。
        user: 以谁的身份跑评测（权限过滤会生效，见文件头说明）。
        top_n: 最终结果保留几条（recall@n 里的 n）。

    返回：
        dict，结构和 schemas.EvalRunResponse 对应：
        {
          "total_cases", "passed", "recall_at_n", "results": [...]
        }
    """
    cases = _load_cases()
    results = []
    passed = 0

    for case in cases:
        # 对每个 case 跑完整 RAG 流水线（权限 + metadata + 检索 + rerank）
        result = run_rag_search(db, user, query=case["query"], top_n=top_n)

        # 本次最终结果命中了哪些文档标题
        returned_titles = [s["document_title"] for s in result.sources]
        # 期望文档里，有多少真的出现在最终结果中
        matched = [t for t in case["expected_documents"] if t in returned_titles]
        # 教学版判定：所有期望文档都出现才算通过（all 判定）
        hit = len(matched) == len(case["expected_documents"])
        if hit:
            passed += 1

        results.append({
            "case_id": case["id"],
            "query": case["query"],
            "expected_documents": case["expected_documents"],
            "hit": hit,
            "matched": matched,
            "returned_documents": returned_titles,
        })

    return {
        "total_cases": len(cases),
        "passed": passed,
        "recall_at_n": round(passed / len(cases), 3) if cases else 0.0,
        "results": results,
    }

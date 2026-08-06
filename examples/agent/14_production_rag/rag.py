"""
rag.py - RAG 编排层

职责：把“检索 + 精排 + 上下文构造”拼成一条完整的 RAG 流水线，
     供两个入口复用：/search 手动检索接口、/tool/run 与 /agent/chat 的检索工具。

为什么要有这一层？
如果没有它，接口和工具都要自己重复写“先检索再 rerank 再拼上下文”，
逻辑散落各处。真实项目里这就是 Service 层：一个入口函数，背后是完整的业务流水线，
上层（接口 / 工具 / Agent）只管调用它拿结果。

本模块的流水线：
    检索(权限+metadata 过滤, top_k)
    -> rerank(精排, top_n)
    -> 构造 sources 列表（回答依据）
    -> 构造 context 文本（给大模型看的内容）
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from permissions import User
from retriever import Candidate, search_chunks
from reranker import RerankedResult, rerank


@dataclass
class RagSearchResult:
    """一条完整 RAG 检索的结果（一个对象同时装三样东西）。"""
    candidates: list[Candidate]                    # 粗排候选（用于 /search 对比展示）
    reranked: list[RerankedResult]                 # 精排结果（最终进入上下文）
    sources: list[dict]                            # 回答依据列表（前端 sources 面板）
    context_text: str                              # 拼给大模型看的上下文
    filtered_documents: int                        # 过滤后参与检索的文档数（观察点）
    dropped_low_score: int                         # 因低于相关性阈值被丢弃的片段数（观察点）
    user_id: str = field(default="")               # 谁检索的（审计用，教学版只展示）


def _build_context(reranked: list[RerankedResult]) -> str:
    """把精排结果拼成一段“带来源标记”的上下文文本。

    为什么每个片段前要加来源标记【文档标题#第几段】？
    1. 大模型看到来源标记，回答时会引用它们，回答质量更高；
    2. 前端 / 日志能追溯“这句话来自哪份文档的哪一段”。
    真实项目里这种标记就是给模型的“引用格式约定”，属于 prompt 工程的一部分。
    """
    parts = []
    for r in reranked:
        doc = r.candidate.document
        chunk = r.candidate.chunk
        # f-string 拼出带来源的片段
        parts.append(f"【来源：{doc.title} 第{chunk.index}段】\n{chunk.content}")
    return "\n\n".join(parts)


def run_rag_search(
    db: Session,
    user: User,
    query: str,
    category: str | None = None,
    tags: str | None = None,
    top_k: int = 20,
    top_n: int = 3,
    min_score: float = 0.0,
) -> RagSearchResult:
    """执行完整 RAG 流水线（所有入口复用这一个函数）。

    参数：
        db: 数据库会话。
        user: 当前用户（权限过滤的依据）。
        query: 检索词。
        category / tags: metadata 过滤（可选）。
        top_k: 召回候选数。
        top_n: 最终保留片段数。
        min_score: 相关性阈值。精排分低于它的片段不进入 sources / 上下文。
                  这是“检索到内容 ≠ 检索到正确答案”的兜底：
                  低相关片段进入回答，会让模型基于错误材料自信地编答案。

    返回：
        RagSearchResult，包含粗排候选、精排结果、sources、上下文文本。
    """
    # 第一步：检索（内部完成权限过滤 + metadata 过滤 + 粗排）
    candidates, filtered_count = search_chunks(
        db, user, query, category=category, tags=tags, top_k=top_k
    )

    # 第二步：精排（只对 top_k 候选重排，取 top_n）
    reranked = rerank(query, candidates, top_n=top_n)

    # 第三步：按相关性阈值过滤，只保留真正相关的片段。
    # 注意：reranked 列表本身保留全部（/search 要展示），
    # 只对“进入回答”的 sources / 上下文做过滤。
    qualified = [r for r in reranked if r.score >= min_score]
    dropped = len(reranked) - len(qualified)

    # 第四步：构造 sources（前端展示“回答依据”）和上下文文本（喂给大模型）
    sources = []
    for r in qualified:
        sources.append({
            "document_id": r.candidate.document.id,
            "document_title": r.candidate.document.title,
            "content": r.candidate.chunk.content,
            "score": round(r.score, 3),
        })

    return RagSearchResult(
        candidates=candidates,
        reranked=reranked,
        sources=sources,
        context_text=_build_context(qualified),
        filtered_documents=filtered_count,
        dropped_low_score=dropped,
        user_id=user.user_id,
    )

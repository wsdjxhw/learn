"""
retriever.py - 检索层（召回阶段）

职责：给定一个查询词，先从“当前用户可见的文档”里召回最相关的若干 chunk（候选）。

这是 RAG 的第一阶段，业界叫“召回 / Recall / Retrieval”。
它只负责“找出可能相关的候选”，不负责排序细节 —— 排序交给 reranker.py。

本模块检索 = 权限过滤 + metadata 过滤 + bigram 关键词打分。

⚠️ 安全设计（真实项目最重要的一条）：
权限过滤必须发生在“数据库查询的 WHERE 条件”里，
也就是 SQL 层面，而不是把库里的 chunk 全捞出来再在内存里过滤。
原因：
1. 性能：数据量一大，全量捞出来再过滤直接内存爆炸；
2. 安全：SQL 只返回用户有权限的数据，泄露风险降到最低；
3. 一致性：任何下游（检索、统计、导出）拿到的都已经是过滤后的数据。

教学版为了讲清楚这条原则，先按“查文档 -> 过滤 -> 再查 chunk”两步走，
真实项目会用一条带 JOIN 的 SQL 一步完成，但原则完全相同。
"""
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from chunker import to_bigrams
from models import Chunk, Document
from permissions import User, can_view_document


class Candidate:
    """一个检索候选 chunk，连同它所属文档的信息。

    为什么要把文档信息带进来？
    后续 metadata 过滤已经发生在 SQL 层，但每个 chunk 来自哪篇文档、
    文档标题是什么，都是检索结果展示和 rerank 需要的信息，
    所以一次检索把这块也带上，避免循环查询数据库。
    """

    def __init__(self, chunk: Chunk, doc: Document, score: float = 0.0) -> None:
        self.chunk = chunk
        self.document = doc
        self.score = score  # 粗排打分，稍后 rerank 会重算


def _visible_documents(db: Session, user: User) -> list[Document]:
    """返回当前用户可见的所有文档（权限过滤的核心）。

    教学版做法：查出“可能相关”的文档集合，再用 can_view_document 判断。
    这样把权限规则（permissions.py）和 SQL 查询解耦，方便讲解。

    真实项目做法：直接把这个条件写进 WHERE：
        WHERE (visibility = 'public' OR owner_id = :me OR :is_admin)
    原理一样，性能更好，因为数据库只返回有权看到的数据。
    """
    all_docs = db.scalars(select(Document)).all()
    # 列表推导式 + can_view_document：只保留当前用户能看的文档
    return [d for d in all_docs if can_view_document(user, d)]


def _filter_by_metadata(docs: list[Document], category: Optional[str], tags: Optional[str]) -> list[Document]:
    """按文档 metadata 过滤可见文档。

    metadata 过滤和关键词检索是两回事：
    - metadata 过滤是“硬条件”：category 不是财务的文档，怎么检索都不会出现；
    - 关键词匹配是“软条件”：相关度打分。
    真实项目里 metadata 过滤放在 SQL 的 WHERE 里，和权限过滤一起，
    目的都是“在打分之前先缩小范围”，省算力、提高准确率。
    """
    result = docs
    if category:
        # 精确匹配分类。真实项目里 category 一般来自固定的枚举/字典表，
        # 避免同一分类出现“财务”和“财务部”两种写法。
        result = [d for d in result if d.category == category]
    if tags:
        # tags 以逗号分隔存储，这里要求文档包含传入的任一标签（"或" 关系）。
        # 真实项目里标签通常单独建一张关联表，这里是教学版简化。
        wanted = {t.strip() for t in tags.split(",") if t.strip()}
        result = [d for d in result if wanted & set(d.tags.split(",")) if d.tags]
    return result


def bigram_overlap(query_text: str, chunk_text: str) -> int:
    """统计查询和 chunk 有多少个相同 bigram（粗分核心）。

    这是模块 13 就用过的核心思想，直接复用：
    查询“报销流程” -> ['报销','销流','流程']
    chunk 含“报销流程” -> 命中 3 个 bigram。
    命中数越多，说明两者共享的字组合越多，越可能相关。
    """
    query_bigrams = set(to_bigrams(query_text))
    chunk_bigrams = set(to_bigrams(chunk_text))
    return len(query_bigrams & chunk_bigrams)


def search_chunks(
    db: Session,
    user: User,
    query: str,
    category: Optional[str] = None,
    tags: Optional[str] = None,
    top_k: int = 20,
) -> tuple[list[Candidate], int]:
    """执行检索：权限过滤 -> metadata 过滤 -> 打分 -> 取 top_k。

    参数：
        db: 数据库会话。
        user: 当前用户（用于权限过滤）。
        query: 用户查询词。
        category / tags: metadata 过滤条件（可选）。
        top_k: 召回多少个候选。

    返回：
        (candidates, filtered_documents_count)
        candidates: 按粗分从高到低排序的候选列表。
        filtered_documents_count: 经过权限+metadata 过滤后参与检索的文档数。
                                 这是教学观察点：能看到过滤条件把范围缩小了多少。

    执行流程：
    1. 拿到可见文档（权限）；
    2. 按 metadata 过滤可见文档；
    3. 把这些文档的所有 chunk 取出；
    4. 对每个 chunk 算 bigram 命中分，过滤掉 0 命中的；
    5. 排序，截断到 top_k。
    """
    visible = _visible_documents(db, user)
    visible = _filter_by_metadata(visible, category, tags)

    # 关键：只有“过滤后可见”的文档才允许进入检索。
    # 文档不可见，它的 chunk 一个都不会出现 —— 这就是文档级权限隔离的效果。
    visible_ids = {d.id for d in visible}
    if not visible_ids:
        return [], 0

    # 一次性把可见文档的所有 chunk 查出来（避免对每篇文档各查一次 = N+1 查询问题）
    all_chunks = db.scalars(
        select(Chunk).where(Chunk.document_id.in_(visible_ids))
    ).all()

    # 打分 + 过滤。理解这行的三个动作：
    # 1. 对每个 chunk 算命中数 score；
    # 2. 只保留 score > 0 的（和查询完全没共现字的 chunk 丢弃）；
    # 3. 组装成 Candidate 对象。
    candidates: list[Candidate] = []
    for chunk in all_chunks:
        score = bigram_overlap(query, chunk.content)
        if score > 0:
            candidates.append(Candidate(chunk=chunk, doc=chunk.document, score=score))

    # 按粗分从高到低排序，截取前 top_k 个作为召回结果。
    # sorted 的 key 传一个“取分函数”，reverse=True 从高到低。
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_k], len(visible)

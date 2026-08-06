"""
reranker.py - 重排序层（精排阶段）

职责：对召回阶段的 top_k 候选重新打分排序，只保留真正相关的 top_n。

为什么检索之后还要 rerank？（这是本模块最重要的概念问题）
1. 粗排（retriever）用的指标很“原始”：只看查询和 chunk 共现多少个 bigram。
   一个泛泛的长段落可能反复出现查询词，共现数量很高，但并不是用户真正想要的答案。
2. 精排（rerank）要综合更多信号：覆盖率、命中位置、标题是否命中、长度是否适中。
   目的是让“真正相关的那一小段”浮到最前面，同时控制进入模型的上下文数量。
3. 真实项目里粗排可能是向量检索（快、宽），精排是交叉编码器 rerank 模型（慢、准），
   两者分工：召回要“广”，精排要“准”。

真实项目用什么做 rerank？
- bge-reranker / Cohere Rerank / 自己微调的交叉编码器模型；
- 它们把 query 和 chunk 拼在一起喂给模型，输出一个相关性分数，准确度高但慢；
- 所以不会对所有 chunk rerank，只对 top_k（几十个）rerank —— 这就是“两阶段检索”。
教学版没有训练 rerank 模型，用几个启发式信号组合打分，把“rerank 到底在干嘛”讲清楚。

本模块的评分公式（权重可调，重点是感受“多信号综合”而不是背公式）：
    final = 0.5 * 覆盖率 + 0.2 * 位置 + 0.2 * 标题命中 + 0.1 * 长度适中
"""
from chunker import to_bigrams
from retriever import Candidate


class RerankedResult:
    """一个精排后的结果，附带“为什么排这么高”的解释。

    把打分拆成 reasons，是为了让学习者能读懂：
    同一句话为什么粗排第 3、精排第 1 —— 每一分从哪来的一目了然。
    真实项目里这个解释就是调试入口：发现排序不对，先看哪个信号拖了后腿。
    """

    def __init__(self, candidate: Candidate, score: float, reasons: list[str]) -> None:
        self.candidate = candidate
        self.score = score
        self.reasons = reasons


def _coverage_score(query_bigrams: set[str], chunk_bigrams: set[str]) -> float:
    """覆盖率：查询的 bigram 有多少比例在 chunk 里出现了。

    和粗排“共现数量”的区别：
    粗排看绝对数量，可能被“一个词反复出现”骗了；
    覆盖率看相对比例，只有 chunk 真正覆盖了查询的大部分内容才算高。
    这就是“报销”反复出现 7 次，也覆盖不了查询里“审批流程”两个字的原因。
    """
    if not query_bigrams:
        return 0.0
    hit = query_bigrams & chunk_bigrams
    return len(hit) / len(query_bigrams)


def _position_score(query_bigrams: set[str], chunk_text: str) -> float:
    """位置分：查询的 bigram 第一次出现在 chunk 的哪个位置，越靠前越高。

    直觉：答案往往集中在开头，一个关键词出现在第 5 个字
    比出现在第 500 个字更可能是真正的答案所在。
    这里用 1/(1 + first_index/total_len) 把“靠前程度”映射到 0~1。
    """
    if not query_bigrams:
        return 0.0
    total = len(chunk_text)
    if total == 0:
        return 0.0
    first_index = total  # 初始化为最后，表示“还没找到”
    for bi in query_bigrams:
        idx = chunk_text.find(bi)  # find：返回第一次出现的下标，找不到返回 -1
        if idx >= 0 and idx < first_index:
            first_index = idx
    if first_index == total:  # 一个都没命中
        return 0.0
    return 1.0 / (1.0 + first_index / total)


def _length_score(text: str) -> float:
    """长度适中分：chunk 太短（丢上下文）或太长（混噪音）都会降权。

    用分段函数做“中间高、两端低”：40 字以下和 500 字以上打折扣。
    真实项目会按 embedding 模型的 max_length 决定上限。
    """
    n = len(text)
    if n < 40:
        return 0.6
    if n > 500:
        return 0.6
    if n < 80 or n > 300:
        return 0.8
    return 1.0


def _title_score(query_bigrams: set[str], title: str) -> float:
    """标题命中分：查询的 bigram 是否命中文档标题。

    直觉：文档标题是最浓缩的主题描述。
    查询命中标题，说明这篇文档整体上就是讲这件事的，
    它的内容比“顺带提了一句”的文档更可信。命中给 1，否则给 0。
    """
    if not query_bigrams:
        return 0.0
    title_bigrams = set(to_bigrams(title))
    return 1.0 if (query_bigrams & title_bigrams) else 0.0


def rerank(query: str, candidates: list[Candidate], top_n: int = 3) -> list[RerankedResult]:
    """对召回候选重新打分排序，返回精排后的 top_n。

    参数：
        query: 用户查询词。
        candidates: retriever 返回的召回候选（数量通常 = top_k）。
        top_n: 最终保留几个（这几个才进入大模型上下文 / 展示给用户）。

    返回：
        按精分从高到低排序的 RerankedResult 列表（已截断到 top_n）。

    流程：
    1. 对每个候选算 4 个信号分；
    2. 加权合成最终分；
    3. 记录理由；
    4. 排序、截断。
    """
    query_bigrams = set(to_bigrams(query))

    results: list[RerankedResult] = []
    for cand in candidates:
        text = cand.chunk.content
        chunk_bigrams = set(to_bigrams(text))
        title = cand.document.title or ""

        cov = _coverage_score(query_bigrams, chunk_bigrams)
        pos = _position_score(query_bigrams, text)
        title_hit = _title_score(query_bigrams, title)
        length = _length_score(text)

        # 加权合成。权重为什么这样设？
        # 覆盖率是最核心的相关性信号，占一半；
        # 位置和标题各两成；长度只是轻微惩罚，占一成。
        final = 0.5 * cov + 0.2 * pos + 0.2 * title_hit + 0.1 * length

        # 覆盖率下限降权：覆盖率是“相关性”最硬的信号。
        # 一个只覆盖查询 1/12 关键词的片段，即使关键词位置很靠前，也基本是巧合匹配
        # （例如“季度规划”与“制度规定”共享“度规”二字）。
        # 真实 rerank 模型没有这种手工规则，它直接学语义；教学版必须靠它防巧合。
        if cov < 0.2:
            final = final * 0.3

        # 组织成可读的理由，这是教学观察点：
        # 能看到“这个 chunk 为什么高/低”，而不是只有一个黑盒分数。
        reasons = [
            f"覆盖率 {cov:.2f}（命中 {len(query_bigrams & chunk_bigrams)}/{len(query_bigrams)} 个关键词）",
            f"位置 {pos:.2f}（关键词首次出现在第 {text.find(next(iter(query_bigrams))) if query_bigrams else -1} 字）",
            f"标题命中 {title_hit:.0f}" + ("：标题含查询词" if title_hit else "：标题不含查询词"),
            f"长度适中 {length:.2f}（共 {len(text)} 字）",
        ]
        if cov < 0.2:
            reasons.append("覆盖率过低（<0.2），综合分降权：此类多为巧合匹配")
        results.append(RerankedResult(candidate=cand, score=final, reasons=reasons))

    # 按精分从高到低排序
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]

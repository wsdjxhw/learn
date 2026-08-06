"""
chunker.py - 文本切分层

职责：把一篇长文档切成适合检索的多个“片段”（chunk）。

为什么必须切分？
- 大模型上下文是有限的，不能把整篇文档直接塞进去；
- 检索是“按片段匹配”的，文档太大会导致匹配粗糙、答案范围太大；
- 回答要能定位到“原文第几段”，方便展示来源。

切分的目标（真实项目里的通用原则）：
1. 语义完整：尽量在段落、句子的边界切，不要从一句话中间劈开；
2. 长度适中：太短丢失语义，太长混入噪音（本模块默认 300 字/段）；
3. 可还原顺序：每段记录 index，回答时能按原文顺序组织。

真实项目还会做：
- 重叠窗口（overlap）：相邻片段保留一部分重叠，避免关键句正好被切开；
- 按标题 / 列表结构切：Markdown 按 ## 标题分节，效果比固定长度好很多；
- 向量化后再切：先 embedding 再按语义聚类。
教学版用“段落优先 + 超长按句子再切”，把最小可行做法讲清楚。
"""
from settings import settings


def split_text(text: str, max_chars: int = None) -> list[str]:
    """把一整篇文本切成多个片段，返回片段字符串列表。

    参数：
        text: 清洗后的整篇文本。
        max_chars: 每个片段的目标字数上限。不传则用 settings 的默认值。

    返回：
        片段列表。这里的顺序就是入库时的 index 顺序。

    实现思路（教学版三步）：
    1. 先把文本按“空行”拆成段落（真实文档段落之间通常有空行）；
    2. 段落本身没超长 -> 直接作为一个片段；
    3. 段落超长 -> 再按句子边界切成多段。
    """
    if max_chars is None:
        max_chars = settings.chunk_max_chars

    # 用空行（\n\n 或 \r\n\r\n）切段落。split() 在字符串中间出现多个分隔符时，
    # 会用“空白字符”整体分割，这比 split("\n") 更鲁棒。
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            # 段落没超长：整个作为一段。语义最完整，优先保留。
            chunks.append(para)
        else:
            # 段落超长：按句子边界切。这里是教学版简化，
            # 用中英文常见的句末标点作为切点，避免把句子从中间劈开。
            chunks.extend(_split_long_paragraph(para, max_chars))
    return chunks


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """把一个超长段落按句子边界切成多段。

    教学版切点集合：。！？；!?; 以及换行。
    为什么用这些标点？
    中文句号“。”是完整语义的最小单位；逗号“，”切开会破坏语义，所以不用它。
    """
    import re

    # re.split 加捕获组 ()：会把分隔符也保留在结果里。
    # 这样切出来的每一段还带着句号，不会把“。”丢掉。
    # 例如 "第一句。第二句！" -> ['第一句。', '第二句！', '']
    parts = re.split(r"(。|！|？|；|!|?|;|\n)", paragraph)

    # 重新拼回带标点的完整句子，同时丢掉空串。
    # 下面这行的写法：把相邻两个元素（句子 + 它的标点）拼起来。
    sentences = []
    buffer = ""
    for part in parts:
        if not part:
            continue
        buffer += part
        # 这个 part 是标点（长度 1 的中英文句末符），说明一句话结束了。
        if part in "。！？；!?;":
            sentences.append(buffer)
            buffer = ""
    if buffer:  # 最后没以标点结尾的残余也保留
        sentences.append(buffer)

    # 再把“句子”按最大长度合并成“片段”。
    result = []
    current = ""
    for sentence in sentences:
        # 单句已经超过上限：只能硬切（教学版简化，真实项目这里要更精细处理）
        if len(sentence) > max_chars:
            if current:
                result.append(current)
                current = ""
            result.append(sentence[:max_chars])
            continue
        # 把下一句并进来不会超长 -> 合并；会超长 -> 先提交当前片段，再开始新片段
        if len(current) + len(sentence) <= max_chars:
            current += sentence
        else:
            if current:
                result.append(current)
            current = sentence
    if current:
        result.append(current)

    return result


def to_bigrams(text: str) -> list[str]:
    """把文本转成中文 bigram（相邻两字）列表，供检索使用。

    为什么用 bigram 而不是直接按词切？
    - 中文没有天然空格，直接“分词”需要词典或模型；
    - bigram 是最便宜的“伪分词”：任何连续两字都算一个特征；
    - “报销流程” -> ['报销', '销流', '流程']，能命中“流程”和“报销”两个常见词。
    这就是模块 13 已经用过的方案，本模块直接复用，但会增加长度/位置等打分维度。
    """
    result = []
    for i in range(len(text) - 1):
        # 跳过带空白的 bigram（跨词的相邻两字没意义）
        two = text[i : i + 2]
        if " " not in two:
            result.append(two)
    return result

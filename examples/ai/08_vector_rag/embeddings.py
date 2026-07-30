import hashlib
import math
import re

VECTOR_DIMENSION = 32


def tokenize(text: str) -> list[str]:
    # tokenize 是“转向量前”的一步：先把连续文本拆成更小的 token。
    # 在真实 embedding 模型里，分词规则通常由模型自己的 tokenizer 决定。
    #
    # 这里仍然不是“真正理解语义”的 embedding，只是为了让本模块不用外部服务也能跑通。
    # 英文按单词切；中文按单字切。这样中文问题里的一部分字，也更容易和文档片段匹配上。
    english_or_number_tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    chinese_tokens = re.findall(r"[\u4e00-\u9fff]", text)
    return english_or_number_tokens + chinese_tokens


def normalize(vector: list[float]) -> list[float]:
    # 归一化会把向量长度缩放到 1。
    # 这样后面比较相似度时，更关注“方向是否接近”，而不是文本越长分数越大。
    length = math.sqrt(sum(value * value for value in vector))
    if length == 0:
        return vector
    return [value / length for value in vector]


def embed_text(text: str) -> list[float]:
    # mock embedding：
    # 1. 先把文本切成 token。这个步骤由 tokenize(text) 完成。
    # 2. 用 hash 把每个 token 固定映射到一个向量位置。
    # 3. 累加后归一化。
    #
    # 真实 embedding 会调用模型，把文本变成能表达语义的高维向量。
    # 这里的目标是学习“文本 -> 向量 -> 相似度检索”的工程链路。
    vector = [0.0] * VECTOR_DIMENSION

    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = digest[0] % VECTOR_DIMENSION
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        vector[index] += sign

    return normalize(vector)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    # cosine similarity 可以理解成两个向量“方向”的接近程度。
    # 分数越高，代表两个文本在这个 mock embedding 空间里越接近。
    if not left or not right or len(left) != len(right):
        return 0.0

    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if left_length == 0 or right_length == 0:
        return 0.0

    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    return dot_product / (left_length * right_length)

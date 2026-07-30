# 向量化 RAG 代码讲解

本模块接在 `04_rag_document_qa` 后面。

04 的检索方式是关键词匹配：

```text
问题里的词在哪些 chunk 里出现更多，哪些 chunk 排前面
```

08 的检索方式是向量相似度：

```text
问题 -> tokenize -> question embedding
chunk -> tokenize -> chunk embedding
比较两个 embedding 的相似度
```

## 文件职责

```text
main.py          FastAPI 接口层
db.py            SQLite 存储 documents、chunks 和 embedding
text_splitter.py 文本切分
embeddings.py    mock embedding 和 cosine similarity
retriever.py     top-k 向量检索
provider.py      mock / DeepSeek 回答生成
```

这种拆分不是为了显得复杂，而是为了让每个文件只负责一类问题。

类比 Java：

- `main.py` 类似 Controller。
- `provider.py` 类似调用外部模型服务的 Service。
- `db.py` 类似 Repository。
- `DocumentCreate`、`AskRequest` 类似请求 DTO。

## 请求入口：`main.py`

`DocumentCreate` 是创建文档的请求体：

```python
class DocumentCreate(BaseModel):
    title: str
    content: str
    chunk_size: int = 500
    overlap: int = 80
```

`BaseModel` 来自 Pydantic。FastAPI 会用它做三件事：

1. 从 JSON 请求体里读取字段。
2. 校验字段类型。
3. 自动生成 `/docs` 里的接口文档。

所以它更像 Java 的请求 DTO，不是数据库表。

## 文档入库链路

`POST /documents` 的核心流程：

```text
payload.content
-> split_text()
-> tokenize(chunk)
-> embed_text(chunk)
-> create_document()
-> SQLite
```

代码里这段列表推导式：

```python
chunk_vectors = [
    {"content": chunk, "embedding": embed_text(chunk)}
    for chunk in chunks
]
```

可以拆成普通循环理解：

```python
chunk_vectors = []
for chunk in chunks:
    item = {"content": chunk, "embedding": embed_text(chunk)}
    chunk_vectors.append(item)
```

列表推导式只是 Python 的简写。这里的学习重点是：每个 chunk 入库前都要先经过“分词 -> 向量化”。

当前代码里 `tokenize(chunk)` 写在 `embed_text(chunk)` 内部。也就是说，业务代码调用 `embed_text()`，但真正发生的是：

```text
chunk 文本
-> tokenize(chunk)
-> token 列表
-> hash 成固定维度数字
-> normalize()
-> embedding
```

## embedding 是什么

在真实 AI 项目里，embedding 是模型把文本转换成的一组数字。

可以先粗略理解成：

```text
文本的“坐标”
```

如果两个文本意思接近，它们的坐标方向通常也会接近。检索时就可以用“问题坐标”去找最接近的“资料片段坐标”。

本模块的 `embeddings.py` 没有调用真实模型，而是用 mock embedding：

```text
分词 -> hash 到 32 维向量 -> 归一化
```

这不是生产级语义检索，但它能让你看懂完整工程结构。

## cosine similarity 是什么

`cosine_similarity()` 用来比较两个向量的方向是否接近。

它解决的问题是：

```text
问题 embedding 和 chunk embedding 到底像不像？
```

返回分数越高，代表越相似。本模块在 `retriever.py` 里用它给每个 chunk 打分。

## 向量检索：`retriever.py`

核心流程：

```text
question -> tokenize(question) -> embed_text(question)
遍历所有 chunk embedding
计算 cosine similarity
过滤 min_score
按 score 倒序排序
返回前 top_k 个
```

`top_k` 和 `min_score` 解决的是两个不同问题：

- `top_k` 控制最多拿几条资料，避免上下文过长。
- `min_score` 控制最低相关性，避免明显不相关的资料进入回答。

真实 RAG 系统里，这两个参数会明显影响答案质量。

## 为什么 SQLite 里保存 JSON

`db.py` 里把 embedding 保存成 `embedding_json`：

```text
[0.1, 0.0, -0.2, ...]
```

SQLite 没有专门的向量类型。为了让初学阶段先能运行，本模块把 list 转成 JSON 字符串保存。

读取时再用：

```python
json.loads(embedding_json)
```

把字符串转回 `list[float]`。

真实项目里通常不会这样全表扫描，而是使用向量数据库或向量索引。

## `/ask` 的输出怎么读

`POST /ask` 返回：

```json
{
  "question": "...",
  "answer": "...",
  "sources": [
    {
      "id": 1,
      "document_title": "...",
      "content": "...",
      "score": 0.5231
    }
  ],
  "chat_provider": "mock",
  "embedding_provider": "mock"
}
```

重点不是先看 answer，而是先看 `sources`。

如果 sources 不对，模型回答通常也不会好。RAG 调试时要先调检索，再调生成。

## 和 04 模块的关键区别

04 模块：

```text
关键词匹配，容易理解，但只能匹配字面出现的词。
```

08 模块：

```text
先转 embedding，再算相似度，结构更接近真实 RAG。
```

当前 08 仍然是教学版，因为 embedding 是 mock 的。它的价值是让你先理解工程链路：

```text
文档切分
chunk embedding 入库
查询 embedding
top-k 相似度检索
sources 返回
模型基于 sources 回答
```

后续可以把 `embed_text()` 替换成真实 embedding API，把 `list_all_chunks()` 替换成向量数据库查询。

## 调试分词和向量

`POST /debug/embedding` 是本模块专门加的观察接口。

它不会入库，也不会调用模型，只做：

```text
text -> tokenize(text) -> embed_text(text) -> 返回 tokens 和 embedding_preview
```

用它可以确认：向量不是凭空出现的，而是文本先被拆成 token，再被转换成一组数字。

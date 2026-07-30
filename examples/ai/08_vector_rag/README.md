# 向量化 RAG

这一节的目标：把前面 `04_rag_document_qa` 里的关键词检索，升级成 embedding 检索。

先把它理解成：

```text
文本 -> chunk -> token -> embedding 向量 -> 算相似度 -> 找 top-k 片段 -> 让模型基于资料回答
```

本模块先使用本地 mock embedding，不需要真实 embedding 服务，也不需要向量数据库。这样可以先跑通链路，再理解每一步解决什么问题。

## 先读

代码讲解：

[VECTOR_RAG_EXPLAINED.md](VECTOR_RAG_EXPLAINED.md)

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\08_vector_rag
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置：

```powershell
Copy-Item .env.example .env
```

没有真实 `DEEPSEEK_API_KEY` 也可以运行，会自动走 mock 回答。

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

如果 8000 端口被占用：

```powershell
python -m uvicorn main:app --reload --port 9000
```

## 测试顺序

1. `GET /health`
2. `POST /debug/embedding`
3. `POST /documents`
4. `GET /documents`
5. `GET /documents/{document_id}/chunks`
6. `POST /ask`

## `POST /debug/embedding` 示例

这个接口用来观察一段文本如何先分词，再转成向量。

请求体：

```json
{
  "text": "RAG 会把 chunk 转成 embedding"
}
```

返回里重点看：

- `tokens`：分词结果。
- `embedding_preview`：向量前几个数字。
- `embedding_dimension`：完整向量维度。

## `POST /documents` 示例

请求体：

```json
{
  "title": "FastAPI 和 RAG",
  "content": "FastAPI 适合构建 AI 应用后端接口。RAG 会先把文档切成 chunk，再把 chunk 转成 embedding，查询时用问题向量检索相似内容。",
  "chunk_size": 60,
  "overlap": 10
}
```

## `POST /ask` 示例

请求体：

```json
{
  "question": "RAG 查询时为什么要用 embedding？",
  "top_k": 3,
  "min_score": 0.05
}
```

返回里重点看：

- `answer`：mock 或 DeepSeek 生成的答案。
- `sources`：向量检索命中的片段。
- `score`：问题向量和 chunk 向量的相似度分数。
- `embedding_provider`：当前是 `mock`，说明 embedding 来自本地教学实现。

## 当前实现边界

本模块的 embedding 是教学版 mock embedding：

```text
chunk -> 分词 -> hash 到固定维度 -> 归一化 -> cosine similarity
```

它能帮助你理解工程链路，但不代表真实语义理解能力。真实项目会换成：

- OpenAI、DeepSeek 或其他 embedding 模型。
- pgvector、Qdrant、Milvus、FAISS 等向量库或向量索引。
- 更完整的 chunk 元数据和召回策略。

## 本课练习

1. 录入两篇主题不同的文档，例如一篇讲 FastAPI，一篇讲 PostgreSQL，再分别提问观察 `sources` 是否命中正确文档。
2. 把 `min_score` 从 `0.05` 提高到 `0.2`，观察命中片段减少时 answer 如何变化。
3. 用 `POST /debug/embedding` 输入同一句话的中英文版本，观察 token 数量和向量预览的变化。
4. 用 `GET /documents/{document_id}/chunks` 查看 `embedding_preview`，解释为什么接口只返回前 6 个数字。
5. 修改 `chunk_size` 和 `overlap`，重新录入同一篇文档，对比 chunk 数量和检索结果。
6. 阅读 `retriever.py`，解释 `top_k` 和 `min_score` 分别解决什么真实工程问题。
7. 设计一个扩展：给 `sources` 增加 `reason` 字段，说明为什么这个片段被选中。要求先判断这个 reason 应该由检索器生成，还是由模型生成。

这些练习的目标不是机械新增接口，而是理解真实 RAG 项目里的向量化、相似度阈值、top-k 召回和 sources 可解释性。

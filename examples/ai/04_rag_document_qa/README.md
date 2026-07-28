# RAG 文档问答

这一节的目标：让 AI 不只是聊天，而是能基于你上传或录入的资料回答问题。

RAG 的完整名字是 Retrieval-Augmented Generation，可以先理解成：

```text
先检索资料，再让模型回答
```

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\04_rag_document_qa
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

## 测试顺序

1. `GET /health`
2. `POST /documents`
3. `GET /documents`
4. `GET /documents/{document_id}/chunks`
5. `POST /ask`

## `POST /documents` 示例

请求体：

```json
{
  "title": "FastAPI 简介",
  "content": "FastAPI 是一个用于构建 API 的 Python Web 框架。它支持类型注解、自动生成文档，并且和 Pydantic 深度集成。",
  "chunk_size": 80,
  "overlap": 10
}
```

## `POST /ask` 示例

请求体：

```json
{
  "question": "FastAPI 有什么特点？",
  "top_k": 3
}
```

## 当前检索方式

当前模块先使用“关键词匹配”做检索。

也就是说：

```text
问题里的词在哪些 chunk 里出现更多，哪些 chunk 就排在前面
```

这不是生产级 RAG，但适合入门，因为你可以清楚看到 RAG 链路：

```text
文档 -> 切分 -> 存储 -> 检索 -> 生成答案 -> 返回 sources
```

后续模块会再升级到 embedding 和向量库。

## 本课练习

1. 用 `POST /documents` 录入一篇短文。
2. 用 `GET /documents/{document_id}/chunks` 查看切分结果。
3. 用 `POST /ask` 提问，观察 `sources` 返回了哪些片段。
4. 修改 `chunk_size` 和 `overlap`，对比切分结果变化。
5. 给 `GET /documents` 增加 `keyword` 查询参数，按标题搜索文档。

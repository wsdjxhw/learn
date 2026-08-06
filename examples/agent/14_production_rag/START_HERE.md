# 先从这里开始

如果只想用 30 分钟抓住本模块核心，按这个顺序：

1. 启动：`uvicorn main:app --reload --port 8015`
2. 打开：`http://127.0.0.1:8015/docs`
3. 调 `POST /demo/seed-docs`，一键导入 4 篇示例文档（默认 alice 身份）
4. 调 `POST /search`，请求体 `{"query": "报销流程怎么走"}`，看两样东西：
   - `raw_candidates`（粗排）和 `reranked_results`（精排）的顺序是不是不一样；
   - 为什么精排把“审批流程”那段提到了标题段前面。
5. 调 `GET /documents`，先不传 key（alice），再看 `X-API-Key: operator-key`（bob）——文档数量从 4 变成 3，bob 看不到 alice 的私有文档。
6. 调 `POST /agent/chat`，用 bob 的身份问“产品路线图三季度上线什么功能”，看它诚实说“资料不足”。
7. 调 `POST /eval/run`，分别用 alice 和 bob 跑，看 recall 从 1.0 变成 0.833。

只读这条核心链路：

```text
main.py 的 /search 接口
-> rag.py run_rag_search()          编排：检索 + 精排 + 阈值过滤
-> retriever.py search_chunks()     权限过滤 + metadata 过滤 + bigram 粗排
-> reranker.py rerank()             覆盖率/位置/标题/长度综合精排
-> provider.py run_agent_chat()     Agent 怎么决定检索、怎么诚实说“资料不足”
```

本节最重要的一句话：

```text
RAG 从“能跑”到“能上线”，差的是四件事：真实文件解析、metadata 过滤、
文档级权限隔离、检索后的 rerank。其中权限隔离做不好，等于把所有文档对所有人开放。
```

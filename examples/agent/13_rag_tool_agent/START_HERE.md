# 先从这里开始

如果只想用 30 分钟抓住本节核心，按这个顺序：

1. 启动：`uvicorn main:app --reload --port 8014`
2. 打开：`http://127.0.0.1:8014/docs`
3. 调 `POST /demo/seed`，写入三篇示例文档
4. 调 `POST /tool/run`，手动执行 `search_documents`，看懂 `sources` 结构
5. 调 `/agent/chat`，分别试这三句话：

```text
公司的报销流程是什么？   -> used_tool=true，sources 有 3 条
你好                     -> used_tool=false，不检索
什么是黑洞               -> used_tool=true，sources 为空，回答说明资料不足
```

只读这条链路：

```text
main.py agent_chat()
-> provider.py decide_next_action()     判断要不要检索
-> tools.py _search_documents()         执行检索
-> rag.py search_documents_in_db()      取 chunks 并排序
-> provider.py generate_final_answer()  组织带 sources 的回答
```

本节最重要的一句话：

```text
RAG 不是一个 /ask 接口，而是 Agent 手里的一个工具：什么时候查、查到什么、没查到怎么办，都由 Agent 和后端决定。
```

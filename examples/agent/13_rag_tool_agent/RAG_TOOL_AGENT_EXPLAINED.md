# RAG 工具智能体代码讲解

这份文档只讲本模块新增的核心链路，不重复模块 10-12 的权限和审计全部细节。

核心流程：

```text
用户问题
-> main.py agent_chat()
-> provider.py decide_next_action()     判断要不要检索
-> 需要检索：
   -> tools.py _search_documents()      工具层：参数校验
   -> rag.py search_documents_in_db()  检索核心：取 chunks + 排序
   -> provider.py generate_final_answer()  组织带 sources 的回答
-> 不需要检索：直接回答
```

## 第一入口：`/agent/chat`

文件：

```text
main.py
```

函数：

```python
agent_chat()
```

这个接口就是完整 RAG Agent。读它时重点看 `steps`，它把一次对话拆成了几个阶段：

```text
user_input -> visible_tools -> model_decision -> tool_execution -> final_answer
```

`model_decision` 是分水岭：决定走“检索分支”还是“直接回答分支”。

```python
decision = decide_next_action(...)
if decision["type"] == "answer":
    return ...  # 不需要检索，直接回答
# 否则继续执行工具
```

## 判断要不要检索：`provider.py`

文件：

```text
provider.py
```

函数：

```python
decide_next_action()
```

这是本模块最重要的决策函数。它只做一件事：根据用户问题决定 `answer`（直接回答）还是 `tool`（调用工具）。

```python
if not allow_tool:
    return {"type": "answer", "answer": "已关闭知识库检索工具..."}
```

`allow_tool=false` 这个参数是教学开关，用来对比“能检索”和“不能检索”的差异。

mock 模式：

```python
_decide_with_mock()
```

用两个触发词列表近似判断：

```python
_KNOWLEDGE_MARKERS = ["报销", "请假", "制度", ...]   # 知识类话题词
_ASK_MARKERS = ["是什么", "什么是", "怎么", ...]      # 问句词
```

命中了就返回工具调用：

```python
return {"type": "tool", "tool_name": "search_documents",
        "arguments": {"query": user_message, "top_k": 3}}
```

DeepSeek 模式：

```python
_decide_with_deepseek()
```

走 OpenAI 兼容协议的 function calling，把 `tool_schemas` 传给模型，模型自己决定：

```python
response = client.chat.completions.create(
    ...,
    tools=tool_schemas,
    tool_choice="auto",
)
```

注意这里 `tools` 参数就是 `tool_registry.py` 里 `to_openai_tool_schema()` 生成的 schema。这是“把 RAG 变成工具”的关键一环：**模型知道有一个 search_documents 工具可选，参数是 query 和 top_k**。

## 工具层：`tools.py`

文件：

```text
tools.py
```

函数：

```python
run_tool()
_search_documents()
```

`run_tool` 是统一分发口，`main.py` 和 Agent 都通过它执行工具。它本身不做检索，只负责“根据工具名找对应的执行函数”。

`_search_documents` 做两件事：

1. 参数校验：`query` 是必填的，没传就返回可读错误，而不是让程序抛异常。

```python
query = str(arguments.get("query", "")).strip()
if not query:
    return {"ok": False, "error": "search_documents 缺少必填参数 query。"}
```

2. top_k 保护：模型可能传一个超大数字，做上限限制。

```python
try:
    top_k = int(arguments.get("top_k", 3))
except (TypeError, ValueError):
    top_k = 3
top_k = max(1, min(top_k, 5))
```

为什么工具层要单独一层？因为真实项目里一个 Agent 可能有几十个工具，每个工具的“参数校验、默认值、错误返回”都散在调用方的话，会非常难维护。统一收敛到 `run_tool` 里，加新工具时只改这里和注册表。

## 检索核心：`rag.py`

文件：

```text
rag.py
```

函数：

```python
search_documents_in_db()
list_all_chunks()
```

`search_documents_in_db` 是检索的完整流程：

```text
1. 取全部 chunks
2. 如果知识库为空 -> 返回 count=0，note="知识库为空"
3. 用 retriever 算相关度，取 top_k
4. 没有相关片段 -> 返回 count=0，note="没有任何片段相关"
5. 有 -> 返回 count + results
```

注意空检索不是抛异常，而是返回 `count=0` 的正常结构。这是本模块刻意设计的：**“检索不到”是业务结果，不是系统错误**。让上层（Agent）能根据 `count` 决定怎么回答。

`list_all_chunks` 用一个 JOIN 把每段文本的所属文档标题带出来：

```python
select(Chunk, Document.title)
.join(Document, Document.id == Chunk.document_id)
```

这就是 sources 里 `document_title` 字段的来源。真实项目这里会换成向量数据库查询。

## 检索打分：`retriever.py`

文件：

```text
retriever.py
```

函数：

```python
tokenize()
score_chunk()
retrieve_relevant_chunks()
```

本模块相对模块 04 的关键改进在 `tokenize()`：中文连续片段切成相邻双字（bigram）。

```python
"报销流程是什么"
-> 报销、销流、流程、程是、是什么
```

这样整句中文也能命中。代价是有误匹配——`score_chunk` 是“问题里的词在 chunk 里出现得越多分越高”，所以“计算”会同时命中报销制度和请假制度。这是教学版故意保留的“缺陷”，方便你理解模块 14 为什么要上 embedding。

## 组织回答：`provider.py`

文件：

```text
provider.py
```

函数：

```python
generate_final_answer()
```

工具执行后，还要把结构化的检索结果组织成用户能看懂的回答。

mock 模式 `_generate_mock_final_answer` 分三条路径：

```python
if not tool_output.get("ok"):
    return f"检索工具执行失败：{tool_output.get('error')}"        # 工具出错

if tool_output.get("count", 0) == 0:
    return "知识库中没有检索到相关资料... 为了避免编造..."          # 检索为空

# 有资料：引用最相关的来源
top = results[0]
return f"最相关的资料来自《{top['document_title']}》第 {top['chunk_index']} 段：..."
```

重点看“检索为空”这条路径——它不调用模型，直接返回诚实说明。这就是“防止幻觉”的实现方式：**后端把空检索拦截下来，不让模型有机会编**。

DeepSeek 模式 `_generate_deepseek_final_answer` 把检索结果作为上下文交给模型，system prompt 里明确要求：

```text
只能基于检索结果回答；如果检索结果为空，明确说明资料不足，不要编造。
```

## sources 从哪里来、到哪里去

sources 的流转：

```text
rag.py 返回 results
-> main.py agent_chat() 里 tool_output.get("results", [])
-> 作为 ChatResponse.sources 返回给前端
-> 同时传给 generate_final_answer() 进回答文本
```

代码里这一行是关键：

```python
sources = tool_output.get("results", [])
reply = generate_final_answer(payload.message, tool_output)
```

`sources` 从工具输出里抽出来，既作为独立字段返回，又参与回答生成。前端拿 `sources` 就能展示“回答依据”，这就是真实产品里“引用来源”功能的雏形。

## 权限和审计：为什么还要查一次

`main.py` 的 `agent_chat` 里，即使工具来自可见列表，后端仍然再查一次权限：

```python
permission = check_tool_permission(auth, tool, decision["arguments"])
```

这是模块 10-12 反复强调的原则：**模型选的工具名不等于可信**。模型可能被 prompt injection 诱导，也可能生成未注册工具名。所以后端必须用注册表 + 权限系统兜底。

审计日志在成功和拒绝两条路径都写：

```python
write_tool_audit_log(db, request_id, auth, tool, allowed, reason, ...)
```

## 如果要给 Agent 加一个新能力

假设你要加一个“查员工通讯录”的工具，一般改：

- `tool_registry.py`：注册新工具和参数 schema。
- `tools.py`：加 `_search_contacts()` 并在 `run_tool` 里分发。
- `provider.py`：mock 模式加触发词；DeepSeek 模式会自动根据 schema 决定。
- `schemas.py`：如果接口要暴露新返回字段，补 DTO。
- `README.md`：补测试命令。

不要把检索逻辑写在 main.py 里，保持“接口层 -> 决策层 -> 工具层 -> 数据层”的分层。

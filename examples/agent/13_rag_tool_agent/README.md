# 13 RAG 工具智能体

本模块解决的问题：前面学的 RAG 只是一个 `/ask` 接口，用户问一次就检索一次。真实 Agent 不是这样的——它要先**判断这个问题需不需要检索**，需要时才调用检索工具，然后把检索到的资料（sources）带进最终回答；检索不到资料时，要诚实说“资料不足”，而不是编造。

本模块是独立可运行模块，但它不是从零开始的：它复用了模块 10-12 的工具注册表、API Key 身份、审计日志，也复用了模块 04 的 RAG 检索能力，把它们组合成一个**把 RAG 当成工具用的 Agent**。

## 学习目标

学完本模块，你应该能讲清楚：

- RAG 从“一个 /ask 接口”变成“Agent 手里的一个工具”意味着什么。
- Agent 怎么判断“什么时候需要检索”。
- 检索结果（sources）怎么进入最终回答，前端怎么展示“回答依据”。
- 检索不到资料时，Agent 为什么必须说明不足，而不是编造。
- 工具注册表、权限检查、审计日志和 RAG 是怎么拼在一起的。

你应该能做：

- 给知识库录入文档，让 Agent 能检索到。
- 手动执行 `search_documents` 工具，看懂返回的 sources 结构。
- 让 Agent 自动决定：知识问题去检索、闲聊不检索、库外问题诚实说不足。
- 用 `allow_tool=false` 对比“能检索”和“不能检索”的差异。

## 和前后模块的关系

本模块继承：

- API Key 认证和角色（模块 10-12）。
- 工具注册表和工具 schema（模块 10-12）。
- 后端权限兜底和工具审计日志（模块 10-12）。
- RAG 检索能力：切分、入库、关键词检索、sources（模块 04）。

本模块新增：

- `search_documents` 工具：把 RAG 检索包装成 Agent 可主动调用的工具。
- Agent 决策层：判断“要不要检索”，而不是用户每次请求都强制检索。
- sources 作为一级字段返回，同时进入最终回答文本。
- 检索为空时“说明不足”的诚实回答路径。
- 中文 bigram 分词：让整句中文问题也能命中，模块 04 只能用单个词命中。

本模块为后面准备：

- 模块 14（生产级 RAG）：会把关键词检索升级成 embedding、加 metadata 过滤和权限隔离。
- 模块 15（数据库工具智能体）：同样的“工具 + 决策 + 审计”模式会用到结构化数据上。
- 模块 17（流式输出）：sources 会变成前端实时展示的一部分。

## 启动方式

```bash
cd examples/agent/13_rag_tool_agent
pip install -r requirements.txt
uvicorn main:app --reload --port 8014
```

打开：

```text
http://127.0.0.1:8014/docs
```

默认 mock 模式，不需要真实模型 API Key。

## 教学 API Key

```text
learner-key   -> viewer
operator-key  -> operator
admin-key     -> admin
```

请求头：

```text
X-API-Key
```

不传时默认是 `learner-key`（viewer 角色）。

## 接口测试顺序

### 1. 确认服务启动

```bash
curl http://127.0.0.1:8014/health
```

要看到：

```text
module = 13_rag_tool_agent
model_mode = mock
```

### 2. 确认身份

```bash
curl http://127.0.0.1:8014/auth/whoami
```

要看到 `user_id = u_learner`、`role = viewer`。换 `-H "X-API-Key: operator-key"` 会变成 operator。

### 3. 查看工具清单

```bash
curl -H "X-API-Key: operator-key" http://127.0.0.1:8014/tools
```

重点看 `search_documents` 的 `description` 和参数：`query`（检索词）、`top_k`（返回几条）。

### 4. 一键写入示例文档

```bash
curl -X POST http://127.0.0.1:8014/demo/seed
```

返回三篇示例文档（报销、请假、行为规范）及其 chunk 数量。也可以用 `POST /documents` 手动录入自己的文档。

### 5. 手动执行检索工具

先用 `/tool/run` 绕过 Agent 决策，直接看工具返回什么：

```bash
curl -X POST http://127.0.0.1:8014/tool/run ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"tool_name\":\"search_documents\",\"arguments\":{\"query\":\"报销流程是什么\",\"top_k\":2}}"
```

你要看：

- `allowed=true`、`permission_reason=权限检查通过`
- `tool_output.count` 检索到几条
- `sources` 数组里每个元素都有 `document_title`、`chunk_index`、`content`、`score`
- score 越高说明越相关

### 6. 场景 A：知识问题，Agent 应该去检索

```bash
curl -X POST http://127.0.0.1:8014/agent/chat ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"message\":\"公司的报销流程是什么？\"}"
```

你要看：

- `used_tool=true`
- `sources` 有 3 条，来源是《公司报销制度》
- `reply` 里引用了最相关片段和来源文档
- `steps` 里有 `model_decision -> tool_execution -> final_answer`

### 7. 场景 B：闲聊，Agent 应该不检索

```bash
curl -X POST http://127.0.0.1:8014/agent/chat ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"message\":\"你好\"}"
```

你要看：

- `used_tool=false`
- `sources` 为空
- `steps` 停在 `model_decision`，没有 `tool_execution`

这就是“Agent 能判断什么时候需要检索”。

### 8. 场景 C：知识库外话题，Agent 应该说明不足

```bash
curl -X POST http://127.0.0.1:8014/agent/chat ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"message\":\"什么是黑洞\"}"
```

你要看：

- `used_tool=true`（Agent 判断这是知识问题，去检索了）
- `sources` 为空（知识库里没有相关文档）
- `reply` 明确说“没有检索到相关资料，为了避免编造，不能凭想象回答”

这就是本模块最重要的验收点之一：**检索不到时诚实说明，而不是编造**。

### 9. 对比：关闭工具后知识问题答不了

```bash
curl -X POST http://127.0.0.1:8014/agent/chat ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: operator-key" ^
  -d "{\"message\":\"公司的报销流程是什么？\",\"allow_tool\":false}"
```

你要看：`used_tool=false`，reply 说“已关闭知识库检索工具，我不知道知识库内容”。这说明 RAG Agent 的能力来自工具，不来自模型本身。

### 10. 查看审计日志

```bash
curl -H "X-API-Key: admin-key" http://127.0.0.1:8014/audit/logs
```

普通用户只能看到自己的日志，admin 能看到全部。

## 代码阅读路线

必须精读：

- `main.py`：`/tool/run` 和 `/agent/chat` 两个接口入口。
- `provider.py`：本模块核心，`decide_next_action()` 判断要不要检索，`generate_final_answer()` 组织带 sources 的回答。
- `tools.py`：`search_documents` 工具的参数校验和默认值处理。
- `rag.py`：`search_documents_in_db()` 检索核心，以及 `list_all_chunks()` 的 JOIN 查询。
- `retriever.py`：`tokenize()` 中文 bigram 分词和 `retrieve_relevant_chunks()` 打分排序。

可以粗读：

- `permissions.py`：模块 10-12 的能力，本模块只保留角色检查和审计日志。
- `tool_registry.py`：工具注册表，本模块只有一个工具。
- `models.py`、`database.py`、`settings.py`：建表和配置，和前面模块一致。
- `schemas.py`：DTO，注意 `sources` 字段在哪里定义。

暂时不用管：

- embedding 和向量数据库（模块 14 再学）。
- 文档权限隔离（模块 14 再学）。
- 检索重排序 rerank（模块 14 再学）。
- 工具失败恢复执行器（模块 12 已学，本模块故意不引入，保持聚焦）。

如果只有 30 分钟，只看这一条链路：

```text
POST /demo/seed                先有知识库
-> POST /agent/chat            让 Agent 判断要不要检索
-> main.py agent_chat()
-> provider.py decide_next_action()   判断要不要检索
-> tools.py _search_documents()      执行检索工具
-> rag.py search_documents_in_db()   取 chunks + 排序
-> provider.py generate_final_answer() 组织带 sources 的回答
```

## 真实项目通常怎么做

真实项目一般会：

- 用 embedding 把文档和问题都转成向量，用向量相似度检索，而不是关键词。
- 用向量数据库（如 pgvector、Milvus、Chroma）管理 chunk。
- 让模型通过 function calling 决定“要不要检索、检索词是什么”。
- 把检索到的 sources 返回给前端，前端展示“引用来源”。
- 检索为空或置信度低时，模型明确说资料不足，或者降级到“人工客服”。
- 对文档做权限隔离：不同用户只能检索到有权限的文档。
- 记录检索日志：谁在什么时候检索了什么、用了哪些 sources。

## 教学版做了哪些简化

- 没有 embedding，用中文 bigram 关键词匹配，会有误匹配（例如“计算”会同时命中报销制度和请假制度）。
- 没有向量数据库，直接在 SQLite 里全表扫描。
- mock 模式用关键词近似“模型判断”，真实模型才靠语义判断。
- 文档用 JSON 直接录入，没有文件上传和解析（模块 14 补）。
- 没有文档级权限隔离，所有角色能检索全部文档（模块 14 补）。
- 只有一个 `search_documents` 工具，刻意不引入多工具编排（模块 03 已学过）。

## 本模块 4 个核心知识点

- RAG 检索要包装成“工具”，让 Agent 自己决定什么时候调用。
- 工具调用前必须做后端权限检查，不能只相信模型选的工具名。
- sources 必须进入最终回答，前端和用户能看出回答依据。
- 检索不到资料时必须诚实说明不足，不能编造答案。

## 面试和真实开发能讲什么

你可以这样讲：

> 我把 RAG 检索封装成了 Agent 的一个工具。Agent 通过 function calling 判断问题是否需要检索：知识类问题主动调用检索工具，拿到相关片段后组织回答；闲聊直接回答；检索不到资料时明确说明知识库不足。检索结果的 sources 会同时进入回答文本和接口返回值，前端可以展示回答依据。工具调用经过注册表和权限检查，并写入审计日志。

## 练习任务

### 练习 1：让 Agent 检索用户自己录入的文档

要求：用 `POST /documents` 录入一篇你自己的文档（例如“产品退货政策”），然后用 `/agent/chat` 问一个基于这篇文档的问题，确认回答引用了这篇文档的 sources。

真实能力：理解知识库内容决定 Agent 能回答什么。

### 练习 2：给检索结果加上“相关度阈值”

要求：在 `rag.search_documents_in_db()` 里加一个 `min_score` 判断：如果最高分的片段分数太低（例如 `< 2`），就当作没有检索到相关结果，走“说明不足”分支。

真实能力：理解 RAG 不能“捞到一点就答”，低置信度检索也要诚实降级。这为模块 14 的 rerank 做准备。

### 练习 3：暴露 `top_k` 对回答质量的影响

要求：分别用 `top_k=1` 和 `top_k=3` 问“公司的报销流程是什么？”，对比 `sources` 数量与最终回答内容，然后用一句话说明为什么真实项目要控制 top_k。

真实能力：理解上下文预算——给模型塞太多不相关片段反而干扰回答。

### 练习 4：给搜索加一个“允许检索的文档范围”

要求：给 `search_documents` 加一个可选参数 `document_title`，只在该文档内检索；mock 决策里支持“用户点名要某篇文档时带上这个参数”。

真实能力：为模块 14 的文档级权限隔离和 metadata 过滤做铺垫，这也是真实项目里“只看自己部门的制度”的常见需求。

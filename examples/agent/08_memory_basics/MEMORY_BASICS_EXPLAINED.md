# Agent 记忆基础代码讲解

这份文档按执行链路解释代码。建议先跑通 `README.md` 的接口，再回来看这里。

## 1. `main.py`：接口层

`main.py` 只负责 HTTP 请求和响应。

它提供四类接口：

- `GET /health`：检查服务、模型模式、数据库配置。
- `POST /memory/extract`：只预览记忆提取，不写数据库。
- `GET /users/{user_id}/memories`：查看某个用户的长期记忆。
- `POST /memory/search`：手动测试当前问题能检索出哪些记忆。
- `POST /agent/chat`：完整聊天链路，包含写消息、提取记忆、保存记忆、检索记忆、生成回答。

`db: Session = Depends(get_db)` 是 FastAPI 的依赖注入。

Java 类比：Controller 方法里声明需要 `Session`，框架自动帮你准备好数据库会话，用完后关闭。

## 2. `/agent/chat` 的完整流程

核心代码在 `agent_chat()`：

```text
add_message(user)
extract_memory_candidates()
upsert_memories()
search_memories()
generate_agent_answer()
add_message(assistant)
return ChatResponse
```

这个顺序是有意设计的。

先保存原始 user message，是为了保留聊天历史。即使没有提取出长期记忆，历史也应该存在。

再提取和保存记忆，是为了让用户本轮刚表达的长期偏好可以立即生效。

最后保存 assistant message，是为了让聊天历史完整。

## 3. `schemas.py`：DTO 和结构契约

`ChatRequest`、`MemoryExtractRequest`、`MemorySearchRequest` 是请求 DTO。

`MemoryCandidate`、`MemoryResponse`、`ChatResponse` 是响应 DTO。

DTO 的价值是让接口结构稳定。ORM Model 以后可能加字段，但前端不一定需要全部看到。

`MemoryType = Literal["preference", "profile", "instruction"]` 限制了记忆类型。

这比随便写字符串更安全，因为后端能提前发现不符合契约的值。

## 4. `models.py`：三张表的职责

`ConversationMessage` 保存聊天历史。

它保存：

- `user_id`
- `role`
- `content`
- `created_at`

它的重点是还原对话，不负责未来复用。

`UserMemory` 保存长期记忆。

它保存：

- `memory_type`
- `key`
- `value`
- `source_text`
- `confidence`
- `last_used_at`

`source_text` 很重要。它保留这条记忆来自哪句原文，后续排查错误记忆时能找到依据。

`MemoryUseLog` 保存记忆使用记录。

当某次回答使用了某条记忆，就写一条日志。后续做 trace、评测、安全排查时都能复用。

## 5. `memory_extractor.py`：从原文到候选记忆

`extract_memory_candidates(text)` 是提取入口。

它调用多个小函数：

- `_extract_language_instruction()`
- `_extract_learning_preference()`
- `_extract_like_or_dislike()`
- `_extract_profile()`

为什么不写成一个巨大函数？

因为真实项目里记忆规则会不断增加。按规则类型拆开，后续新增和测试会更容易。

本模块用规则提取，是为了让无 key 模式稳定可运行。学完结构化输出后，你也可以把这里替换成“模型输出 JSON + Pydantic 校验”。

## 6. `memory_store.py`：记忆读写层

`add_message()` 写聊天历史。

`upsert_memories()` 写长期记忆。它不是简单 insert，而是：

- 先按 `user_id + memory_type + key` 查旧记录。
- 查到就更新。
- 查不到才插入。

这样可以避免 `reply_language` 这类记忆无限重复。

`search_memories()` 做教学版检索。它先查出当前用户的记忆，再用 `_score_memory()` 打分。

重点不是打分算法多高级，而是边界正确：

```text
只能查当前 user_id 的记忆
只把相关记忆放入上下文
使用过的记忆要记录 last_used_at 和 MemoryUseLog
```

## 7. `context_builder.py`：把记忆变成上下文

数据库里的 ORM 对象不能直接丢给模型。

`build_memory_context()` 会把记忆转换成短文本：

```text
可复用的长期记忆：
1. [instruction] reply_language = 中文
2. [profile] learning_level = 初学者
```

这一步属于上下文工程。长期记忆只有进入模型上下文，才会影响模型回答。

## 8. `provider.py`：mock 和 DeepSeek

`generate_agent_answer()` 会根据配置决定走 mock 还是真实模型。

mock 模式：

- 不需要 API Key。
- 输出稳定。
- 适合观察记忆链路。

DeepSeek 模式：

- 使用 `openai` Python 包。
- 通过 `base_url` 调用 DeepSeek 的 OpenAI 兼容接口。
- system prompt 明确要求模型只能使用用户问题和长期记忆，不要编造个人信息。

## 9. 这个模块和前后模块的连接

和 `07_short_term_state` 的连接：

- 07 保存一次 run 的执行现场。
- 08 保存跨多轮请求可复用的长期信息。

和 `06_context_engineering` 的连接：

- 06 讲模型输入由哪些部分组成。
- 08 把长期记忆变成其中一个上下文来源。

和 `09_memory_governance` 的连接：

- 08 只做基础写入和复用。
- 09 会处理删除、过期、更新策略和敏感信息拒绝写入。

# 记忆治理代码讲解

建议先按 `README.md` 跑通接口，再读这份文档。

## 1. `main.py`：治理接口入口

`main.py` 是 Web API 层。

它提供：

- `POST /memory/extract`：预览候选记忆和拒绝原因。
- `GET /users/{user_id}/memories`：查看用户记忆。
- `PATCH /users/{user_id}/memories/{memory_id}`：修正记忆。
- `DELETE /users/{user_id}/memories/{memory_id}`：软删除记忆。
- `POST /memory/expire-scan`：模拟过期扫描。
- `POST /agent/chat`：完整聊天、提取、治理、保存、检索、回答链路。

`db: Session = Depends(get_db)` 是 FastAPI 依赖注入。

Java 类比：Controller 方法声明需要数据库会话，框架自动创建并注入，用完后关闭。

## 2. `/agent/chat` 的治理链路

核心流程：

```text
add_message(user)
extract_memory_candidates()
screen_memory_candidates()
upsert_memories()
record_rejections()
search_memories()
generate_agent_answer()
add_message(assistant)
```

和 08 模块相比，新增了两步：

- `screen_memory_candidates()`：敏感信息过滤。
- `record_rejections()`：记录拒绝动作。

这体现真实项目原则：长期记忆不是只会写，还要先判断能不能写。

## 3. `models.py`：治理字段

`UserMemory` 相比 08 模块新增了：

- `status`：`active`、`expired`、`deleted`。
- `expires_at`：过期时间。
- `deleted_at`：删除时间。
- `delete_reason`：删除原因。

这些字段直接决定检索行为。

`search_memories()` 只使用：

```text
status = active
并且没有过期
```

这保证用户删除或过期的记忆不会继续进入模型上下文。

## 4. `memory_safety.py`：敏感信息过滤

`SENSITIVE_PATTERNS` 是敏感信息规则表。

每条规则包含：

- `risk_type`：风险类型，例如 `password`。
- `pattern`：正则表达式。
- `reason`：给前端或日志看的拒绝原因。

`screen_memory_candidates()` 会逐条检查候选记忆的：

- `source_text`
- `value`

任意一个命中敏感规则，就拒绝保存。

这里有一个重要工程点：过滤发生在入库之前。不能先保存敏感信息，再指望后面清理。

## 5. `memory_store.py`：读写和治理规则

`upsert_memories()` 负责创建或更新记忆。

如果同一用户、同一 `memory_type`、同一 `key` 已经存在，就更新旧记录。这样避免同一个长期偏好出现多条冲突记录。

如果旧记录是 `deleted`，用户后来重新表达同一个偏好，系统会重新激活它。

这对应一个真实产品判断：删除表示“当前不要用”，不一定表示“永远禁止再次记住此类信息”。

`soft_delete_memory()` 把记忆标记为 `deleted`。

软删除后：

- 默认列表看不到。
- 检索不会返回。
- 审计日志仍能看到删除动作。

`expire_due_memories()` 模拟定时任务。

它会找到：

```text
status = active
expires_at <= now
```

然后把这些记忆标记为 `expired`。

## 6. `to_memory_response()`：为什么要计算 `is_expired`

有时一条记忆的 `status` 还是 `active`，但 `expires_at` 已经早于当前时间。

如果定时任务还没跑，这条记录从数据上看还没被改成 `expired`。

所以响应 DTO 里额外返回：

```text
is_expired
```

这样前端和调试接口能看出它已经到期。

同时 `search_memories()` 会实时判断过期状态，不依赖过期扫描一定已经执行。

## 7. `context_builder.py`：只构造可用记忆

`build_memory_context()` 接收的是已经被检索函数过滤过的记忆。

这意味着模型看到的上下文已经排除了：

- deleted
- expired
- rejected sensitive memory

上下文工程和记忆治理是连在一起的。模型只能使用你放进上下文的内容，所以治理规则必须在上下文构造之前生效。

## 8. `provider.py`：mock 和 DeepSeek

mock 模式返回稳定文本，方便观察治理链路。

DeepSeek 模式使用：

```text
OpenAI(api_key=..., base_url=...)
```

通过 OpenAI 兼容协议调用 DeepSeek。

system prompt 明确说明：

- 只能使用用户本轮问题和通过治理过滤的长期记忆。
- 不能使用已删除、已过期或被拒绝保存的敏感信息。

注意：prompt 不是安全边界的全部。真正的安全边界在后端检索和过滤逻辑里。

## 9. 学完本模块应该能解释的问题

你应该能回答：

- 为什么聊天历史和长期记忆要分表？
- 为什么长期记忆要有 `status`？
- 为什么删除后不能继续检索？
- 为什么过期判断不能只靠前端？
- 为什么敏感信息过滤要在入库前？
- 为什么记忆更新要留下审计日志？

如果这些问题能讲清楚，说明你已经从“会做记忆功能”进入“会做可上线的记忆功能”。

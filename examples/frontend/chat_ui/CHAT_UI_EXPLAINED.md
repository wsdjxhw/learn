# 前端聊天页面代码讲解

本模块把前面学过的多个后端能力组合到一个页面里。

它的重点不是“页面好不好看”，而是理解：

```text
前端如何组织会话、消息、任务状态和 sources
```

如果你还不熟悉 HTML、CSS、JavaScript、DOM、事件、`fetch()`、`async/await`，先读：

[FRONTEND_BASICS.md](FRONTEND_BASICS.md)

## 文件职责

```text
main.py             FastAPI 接口层和静态文件服务
database.py         SQLite 存储 sessions、messages、chat_tasks、task_sources
worker.py           后台任务处理器
provider.py         mock assistant 回复
retriever.py        教学版 sources 检索
static/index.html   页面结构
static/styles.css   页面样式
static/app.js       页面交互和接口调用
```

类比 Java：

- `main.py` 类似 Controller。
- `database.py` 类似 Repository。
- `worker.py` 类似 Job Handler。
- `SessionCreate`、`MessageCreate` 类似请求 DTO。

## provider 层

`provider.py` 有一个统一入口：

```python
generate_reply(user_message, sources, history)
```

它会根据 `.env` 自动选择：

```text
有 DEEPSEEK_API_KEY -> 调用真实 DeepSeek
没有 DEEPSEEK_API_KEY -> 使用 mock 回复
```

这样模块仍然满足“无 key 也能跑通”，同时也能在配置真实 key 后观察真实模型回答。

注意：DeepSeek key 只在后端读取。浏览器里的 JavaScript 不应该直接拿模型服务密钥。

## 为什么这个模块仍然有后端

前端页面不能凭空显示会话和消息。

它需要后端提供这些接口：

```text
GET  /api/sessions
POST /api/sessions
GET  /api/sessions/{session_id}/messages
POST /api/sessions/{session_id}/messages
GET  /api/tasks/{task_id}
GET  /api/tasks/{task_id}/events
```

所以本模块用一个小型 FastAPI 服务同时提供：

```text
静态页面
后端 API
SQLite 存储
后台任务
```

这样你可以先在一个目录里跑通完整链路。

## 页面入口：`GET /`

`main.py` 里：

```python
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
```

这表示浏览器访问 `/` 时，FastAPI 返回 `static/index.html`。

页面加载后，浏览器会继续请求：

```text
/static/styles.css
/static/app.js
/static/app-icon.svg
```

## 会话列表

`GET /api/sessions` 返回：

```json
{
  "items": [
    {
      "id": 1,
      "title": "学习聊天",
      "message_count": 2
    }
  ]
}
```

`app.js` 里的 `renderSessions()` 会把这些数据渲染到左侧。

这里的学习重点是：

```text
前端不直接读数据库
前端通过 HTTP API 拿数据
```

## 消息历史

切换会话时，前端调用：

```text
GET /api/sessions/{session_id}/messages
```

返回 user 和 assistant 消息。

`renderMessages()` 根据 `role` 决定消息样式：

```text
user      靠右
assistant 靠左
```

这和真实聊天产品的基本结构一致。

## 发送消息

前端提交表单后调用：

```text
POST /api/sessions/{session_id}/messages
```

后端做四件事：

1. 保存 user 消息。
2. 创建 chat_task。
3. 用 `BackgroundTasks.add_task()` 启动后台处理。
4. 立刻返回 `task_id`。

注意：接口不会等待 assistant 回复生成完成。

这复用了前面后台任务模块学过的思想。

## 短期记忆

消息历史展示和短期记忆不是一回事。

消息历史展示是：

```text
前端调用 GET /api/sessions/{session_id}/messages
把历史消息显示在页面上
```

短期记忆是：

```text
后台任务生成 assistant 回复前
从 messages 表读取当前会话最近几条消息
交给 provider 作为上下文
```

`worker.py` 里：

```python
history = list_recent_messages(session_id=session_id, limit=8)
reply = generate_reply(
    user_message=user_message,
    sources=sources,
    history=history,
)
```

`limit=8` 表示最多读取最近 8 条消息。

为什么要限制数量？

```text
会话会越来越长
如果每次都把全部历史传给模型，prompt 会越来越大
成本和延迟都会上升
```

真实项目通常按 token 数裁剪上下文，而不是只按消息条数。

## sources 如何传给真实模型

`sources` 的结构是：

```json
{
  "title": "...",
  "snippet": "...",
  "score": 1.0
}
```

它不是聊天消息，没有 `role` 和 `content` 字段。

所以不能直接把 sources 塞进 DeepSeek 的 `messages` 列表里。正确做法是先把 sources 整理成 context 文本：

```text
[source 1] title=..., score=...
snippet...
```

然后放进 system prompt 或 user content 里。

## SSE 任务事件

前端拿到 `task_id` 后，调用：

```javascript
subscribeTaskEvents(payload.task.id)
```

它会创建浏览器原生的 `EventSource`：

```javascript
const source = new EventSource(`/api/tasks/${taskId}/events`);
```

这表示：

```text
前端建立一条持续连接
后端通过这条连接持续发送任务状态事件
```

后端接口是：

```text
GET /api/tasks/{task_id}/events
```

后端会发送：

```text
event: status
event: sources
event: done
event: task_error
```

这样前端不用自己每隔 600 毫秒请求一次任务接口。

## 保留普通任务查询

本模块仍然保留：

```text
GET /api/tasks/{task_id}
```

它适合在 `/docs` 里调试，也适合做“点击刷新一次”的场景。

两种方式的区别：

```text
普通查询：前端主动问一次
SSE：前端连上后，后端主动推状态
```

SSE 更适合任务状态变化、模型流式输出、进度条更新这类场景。

## sources 展示

任务成功后，`GET /api/tasks/{task_id}` 会返回：

```json
{
  "status": "succeeded",
  "sources": [
    {
      "title": "后台任务",
      "snippet": "...",
      "score": 3.0
    }
  ]
}
```

`renderSources()` 会把它们显示到右侧。

这一步把 RAG 模块里的 sources 概念接到了前端页面上。

## 为什么要转义 HTML

`app.js` 里有：

```javascript
escapeHtml(value)
```

原因是用户输入不能直接拼进 `innerHTML`。

如果用户输入：

```html
<script>alert(1)</script>
```

前端必须把它当普通文本显示，而不是当页面代码执行。

这属于前端安全的基础意识。

## 本模块真正要掌握什么

学完这个模块后，应该能说清楚：

- 页面如何读取会话列表。
- 页面如何读取某个会话的消息历史。
- 消息历史展示和短期记忆有什么区别。
- 后端为什么要限制带入 provider 的历史消息数量。
- 发送消息为什么先返回 `task_id`。
- 前端如何通过 SSE 接收任务状态。
- assistant 消息为什么要任务完成后再刷新。
- sources 如何从后端返回并展示到页面。
- 为什么前端不能直接信任用户输入。

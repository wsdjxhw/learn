# 前端聊天页面

这一节的目标：把前面学过的后端接口组合成一个可使用的聊天页面。

更准确地说，这不是完整的“前端课程”，而是 AI 应用路线里的第一个前端集成模块。它只补足理解这个页面必须用到的最小前端知识：

```text
HTML 负责页面结构
CSS 负责页面样式
JavaScript 负责调用后端接口和更新页面
```

然后用这三件事看懂完整链路：

```text
会话列表 -> 消息历史 -> 发送消息 -> 创建后台任务 -> 轮询任务状态 -> 展示 assistant 回复和 sources
```

## 先读

如果你还没系统学过前端，先读：

[FRONTEND_BASICS.md](FRONTEND_BASICS.md)

代码讲解：

[CHAT_UI_EXPLAINED.md](CHAT_UI_EXPLAINED.md)

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\frontend\chat_ui
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置：

```powershell
Copy-Item .env.example .env
```

默认 `.env.example` 里的 DeepSeek key 是占位值，所以会走 mock 回复。要接入真实 DeepSeek，再把 `.env` 改成：

```text
DEEPSEEK_API_KEY=你的真实 key
DEEPSEEK_MODEL=deepseek-v4-flash
```

注意：这个 key 只在后端 `provider.py` 使用，不应该暴露给浏览器前端。

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开页面：

```text
http://127.0.0.1:8000/
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

如果端口被占用：

```powershell
python -m uvicorn main:app --reload --port 9000
```

## 页面包含什么

- 左侧：会话列表和新建会话。
- 中间：消息历史、会话标题、发送框。
- 右侧：后台任务状态和 sources。

## 本模块到底学什么

本模块主要学习前端如何消费后端 API：

- 页面打开后如何请求会话列表。
- 点击会话后如何请求消息历史。
- 点击发送后如何 `POST` 用户消息。
- 后端返回 `task_id` 后，前端如何轮询任务状态。
- 任务成功后如何刷新 assistant 消息。
- assistant 回复前如何读取最近几条历史消息作为短期记忆。
- 后端返回 sources 后，前端如何展示来源。
- 用户输入展示到页面前为什么要做 HTML 转义。

本模块暂时不系统学习：

- React、Vue、Svelte 等框架。
- npm、打包工具、组件化工程。
- 路由、状态管理、前端构建发布。
- 复杂 UI 动画或完整设计系统。

这些会在真正需要前端工程化时再展开。

## 接口测试顺序

1. `GET /health`
2. `GET /api/sessions`
3. `POST /api/sessions`
4. `GET /api/sessions/{session_id}/messages`
5. `POST /api/sessions/{session_id}/messages`
6. `GET /api/tasks/{task_id}`
7. 打开 `/` 观察页面如何轮询任务状态。

## `POST /api/sessions/{session_id}/messages` 示例

请求体：

```json
{
  "message": "前端如何轮询后台任务并展示 sources？"
}
```

返回里重点看：

- `user_message`：刚保存的用户消息。
- `task`：后台任务，初始状态通常是 `pending`。
- `task_url`：前端应该轮询的任务地址。

## 任务状态

任务会经历：

```text
pending -> running -> succeeded
```

如果消息里包含：

```text
FAIL_TASK
```

后台任务会模拟失败，状态变成：

```text
failed
```

这个入口用于练习前端如何展示失败状态。

## 短期记忆

本模块现在包含两层“历史”：

```text
消息历史展示：前端把 messages 表里的历史消息显示出来
短期记忆：后端生成回复前读取最近几条 messages 作为上下文
```

区别很重要：

- 只展示历史：用户看得到过去聊了什么，但 assistant 生成回复时不一定知道。
- 使用历史：后端把最近消息传给 provider，assistant 才能基于上一轮内容回复。

本模块默认读取当前会话最近 8 条消息。真实项目通常会按 token 数裁剪，而不是简单按条数裁剪。

## 当前实现边界

本模块为了学习清晰，先使用：

- SQLite 保存会话、消息、任务和 sources。
- 默认 mock provider 生成 assistant 回复。
- 配置真实 `DEEPSEEK_API_KEY` 后，可以切换成 DeepSeek provider。
- 简单关键词检索生成 sources。
- 轮询任务状态，不做 WebSocket 或 SSE。

真实项目后续可以替换成：

- React / Vue / Svelte 等前端框架。
- 真实聊天历史 API。
- 真实 RAG sources。
- 流式输出。
- 登录态和用户隔离。

## 本课练习

1. 新建两个会话，分别发送消息，观察左侧 message_count 和会话切换。
2. 发送一条包含 `sources`、`任务` 或 `日志` 的消息，观察右侧 sources 如何变化。
3. 在同一个会话里连续发送两条消息，观察第二次 assistant 回复里的“短期记忆”是否提到上一条用户消息。
4. 新建另一个会话再发送消息，确认它不会记住上一个会话的内容。
5. 发送包含 `FAIL_TASK` 的消息，观察任务失败后页面和接口分别返回什么。
6. 修改会话标题，刷新页面，确认标题仍然保存。
7. 阅读 `app.js`，画出“发送消息 -> 返回 task_id -> 轮询任务 -> 刷新消息”的完整链路。
8. 设计一个扩展：把任务轮询改成 SSE。要求先说明轮询和 SSE 各自的优缺点。

这些练习的目标是理解前端如何消费后端能力，而不是只做页面样式。

# 带聊天历史的 AI 接口

这一节的目标：让 `/chat` 不再是一次性对话，而是能把聊天记录保存到 SQLite。

你要理解的链路：

```text
创建会话
-> 用户发送消息
-> 保存 user 消息
-> 读取历史消息
-> 调用 mock 或 DeepSeek
-> 保存 assistant 回复
-> 返回结果
```

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\02_chat_history
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

## 配置 DeepSeek

默认 `.env` 里是占位值，所以会走 `mock` 模式。

如果要调用真实 DeepSeek，把 `.env` 改成：

```text
DEEPSEEK_API_KEY=你的 deepseek key
DEEPSEEK_MODEL=deepseek-v4-flash
```

## 接口顺序

1. `POST /sessions`

创建会话，请求体：

```json
{
  "title": "我的第一个 AI 会话"
}
```

2. `GET /sessions`

查看会话列表，找到刚创建的 `id`。

3. `POST /sessions/{session_id}/chat`

给某个会话发送消息，请求体：

```json
{
  "message": "请用一句话解释什么是 SQLite",
  "system_prompt": "你是一个耐心的编程老师"
}
```

4. `GET /sessions/{session_id}/messages`

查看这个会话的历史消息。

## 本课练习

1. 创建一个会话。
2. 在同一个会话里发送两条消息。
3. 查看历史消息，确认 user 和 assistant 都被保存了。
4. 给 `GET /sessions` 增加一个 `keyword` 查询参数，按标题搜索会话。

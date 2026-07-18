# 逐段讲解

这一节进入真正 AI 应用会遇到的问题：聊天历史。

## 为什么要保存历史

一次性聊天只需要：

```text
用户问题 -> 模型回复
```

但真正的聊天应用需要：

```text
会话 -> 多条消息 -> 带着历史继续问
```

否则用户第二次问“那它有什么优点？”时，模型不知道“它”指的是什么。

## 文件分工

`main.py`

接口层，类似 Java Controller。

它负责定义：

- `POST /sessions`
- `GET /sessions`
- `POST /sessions/{session_id}/chat`
- `GET /sessions/{session_id}/messages`

`db.py`

数据层，类似 Java 里的 Repository 或 DAO。

它负责：

- 初始化表
- 新增会话
- 查询会话
- 新增消息
- 查询消息

`provider.py`

模型调用层。

它负责：

- 判断使用 mock 还是 DeepSeek
- 生成助手回复

## 数据表

`sessions`

保存会话：

```text
id
title
created_at
```

`messages`

保存消息：

```text
id
session_id
role
content
created_at
```

`role` 有两个常用值：

- `user`：用户消息
- `assistant`：AI 回复

## 关键代码链路

```python
user_message = add_message(...)
```

先保存用户消息。

```python
model_messages = [
    {"role": "system", "content": payload.system_prompt},
    *list_messages_for_model(session_id),
]
```

再读取历史消息，拼成模型需要的格式。

```python
reply_text = generate_reply(model_messages)
```

然后调用 mock 或 DeepSeek 生成回复。

```python
assistant_message = add_message(...)
```

最后保存 AI 回复。

## 和 Java 的类比

```text
FastAPI main.py       -> Spring Controller
Pydantic BaseModel    -> Request DTO
db.py                 -> Repository / DAO
provider.py           -> Service for model provider
SQLite                -> 本地数据库
```

你现在只要能说清楚这条链路，这节就算掌握：

```text
请求 -> Controller -> DB 保存 user -> Provider 生成 reply -> DB 保存 assistant -> 响应
```

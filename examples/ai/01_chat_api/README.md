# 最小 DeepSeek 聊天 API

这一节不是先追求复杂功能，而是先看懂 AI 应用后端最常见的分层：

- `main.py`：接收 HTTP 请求，返回 HTTP 响应。
- `provider.py`：负责和 DeepSeek 模型服务交互。

DeepSeek 的 API 兼容 OpenAI SDK，所以代码里仍然使用 `openai` 这个 Python 包，但配置的是 DeepSeek 的地址和密钥。

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\01_chat_api
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置模板：

```powershell
Copy-Item .env.example .env
```

打开 `.env`，填入你的 DeepSeek Key：

```text
DEEPSEEK_API_KEY=你的 deepseek key
DEEPSEEK_MODEL=deepseek-v4-flash
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口页面：

```text
http://127.0.0.1:8000/docs
```

## 没有 Key 也能运行

如果没有设置 `DEEPSEEK_API_KEY`，接口会自动使用 `mock` 模式。

`mock` 模式不会调用真实模型，只返回一段假回复。它的作用是让你先确认：

- FastAPI 服务能启动。
- `/chat` 接口能接收 JSON。
- `main.py` 能调用 `provider.py`。
- 响应能正常返回给浏览器。

## 有 Key 时

如果 `.env` 里有：

```text
DEEPSEEK_API_KEY=你的 deepseek key
```

`provider.py` 会调用真实 DeepSeek 模型。

## 测试 `/chat`

在 `/docs` 页面里找到：

```text
POST /chat
```

请求体示例：

```json
{
  "message": "请用一句话解释 FastAPI",
  "system_prompt": "你是一个耐心的编程老师"
}
```

## 本课练习

1. 打开 `/health`，确认当前 `provider` 是 `mock` 还是 `deepseek`。
2. 调用 `/chat`，确认能返回 `reply`。
3. 修改 `DEEPSEEK_MODEL`，观察 `/health` 里的模型名是否变化。
4. 给 `/chat` 的返回结果新增一个字段 `message_length`。

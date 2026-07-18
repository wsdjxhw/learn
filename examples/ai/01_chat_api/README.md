# 最小聊天 API 示例

这个示例用来理解 AI 应用后端的基本结构：

- `main.py` 负责 Web API
- `provider.py` 负责和模型提供方交互

你先不要追求“接入所有平台”，先看懂分层思路：
- 接口层接收请求
- 业务层组织消息
- provider 层调用模型

运行前需要设置环境变量：

- `OPENAI_API_KEY`

安装依赖后启动：

```bash
uvicorn main:app --reload
```

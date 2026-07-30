# 认证、限流和日志

这一节的目标：补齐 AI API 被真实调用时必须面对的基础安全和可观测性。

前面的接口大多是：

```text
谁都能调用 -> 调完只返回结果
```

真实项目至少要回答这些问题：

```text
谁在调用？
一分钟内能调用多少次？
请求成功还是失败？
模型调用花了多少？
出错时前端能不能拿到统一格式？
```

## 先读

代码讲解：

[AUTH_RATE_LIMIT_LOGGING_EXPLAINED.md](AUTH_RATE_LIMIT_LOGGING_EXPLAINED.md)

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\10_auth_rate_limit_logging
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制配置：

```powershell
Copy-Item .env.example .env
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

如果端口被占用：

```powershell
python -m uvicorn main:app --reload --port 9000
```

## 配置说明

`.env.example` 里有：

```text
APP_API_KEYS=dev-key-123,teacher-key-456
RATE_LIMIT_PER_MINUTE=5
DEEPSEEK_API_KEY=put-your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-v4-flash
```

重点区分两个 key：

- `APP_API_KEYS`：访问你自己这个 FastAPI 服务的 API Key。
- `DEEPSEEK_API_KEY`：你的服务调用 DeepSeek 时使用的外部模型密钥。

没有真实 `DEEPSEEK_API_KEY` 时会走 mock 模式。

## 测试顺序

1. `GET /health`
2. 不带 `X-API-Key` 调 `POST /chat`，观察 401。
3. 带错误 `X-API-Key` 调 `POST /chat`，观察 403。
4. 带 `X-API-Key: dev-key-123` 调 `GET /auth/check`。
5. 带 `X-API-Key: dev-key-123` 调 `POST /chat`。
6. 连续调用 `POST /chat` 超过 `RATE_LIMIT_PER_MINUTE`，观察 429。
7. 调 `GET /logs/requests` 查看请求日志。
8. 调 `GET /logs/errors` 查看错误日志。
9. 调 `GET /logs/model-calls` 查看模型调用日志。
10. 调 `GET /stats/costs` 查看教学版成本统计。

## `POST /chat` 示例

请求头：

```text
X-API-Key: dev-key-123
```

请求体：

```json
{
  "message": "请解释为什么 AI API 需要鉴权和限流。",
  "system_prompt": "You are a helpful assistant. Answer in Chinese."
}
```

返回里重点看：

- `reply`：mock 或 DeepSeek 回复。
- `usage`：教学版 token 和成本估算。
- `rate_limit`：当前 key 的限流额度和剩余次数。

## 统一错误响应

错误返回统一是：

```json
{
  "error": {
    "type": "http_error",
    "message": "Missing X-API-Key header",
    "status_code": 401
  }
}
```

这样前端不用分别适配 `detail`、`message`、`error` 等不同字段。

## 当前实现边界

本模块为了学习清晰，先使用：

- SQLite 保存日志。
- 内存字典做限流。
- 教学版 token 和成本估算。

真实项目通常会继续升级：

- 请求日志写入专门的日志系统。
- 限流状态存 Redis。
- 成本优先使用模型服务商返回的真实 usage。
- API Key 存数据库并支持禁用、过期和权限范围。

## 本课练习

1. 不带 `X-API-Key` 调 `/chat`，再查 `/logs/errors`，确认错误被记录。
2. 带错误 key 调 `/chat`，对比 401 和 403 的区别。
3. 连续调用 `/chat` 直到出现 429，说明为什么限流要按调用方区分。
4. 成功调用一次 `/chat`，再查 `/logs/model-calls` 和 `/stats/costs`，把一次模型调用和成本统计对应起来。
5. 故意传空 `message`，观察统一错误响应和错误日志。
6. 设计一个扩展：给 `APP_API_KEYS` 增加“只读 key”和“可调用模型 key”两种权限。要求说明日志查询接口和 `/chat` 应该分别允许哪种 key 调用。

这些练习的目标是理解真实 AI API 的安全边界、限流策略、日志留痕、错误响应和成本可见性。

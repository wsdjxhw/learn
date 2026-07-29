# 后台任务和状态查询

这一节的目标：理解“耗时任务不应该一直阻塞接口”。

很多 AI 应用会遇到耗时任务，例如：

- 解析长文档
- 调用模型生成长报告
- 批量处理文件
- 生成知识库索引

这类任务通常不应该让用户一直等在同一个 HTTP 请求里。

更常见的流程是：

```text
提交任务 -> 立刻返回 task_id -> 后台慢慢处理 -> 前端查询任务状态
```

## 启动

进入目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\05_background_tasks
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

## 测试顺序

1. `GET /health`
2. `POST /summary-tasks`
3. `GET /summary-tasks/{task_id}`
4. `GET /summary-tasks`

## 创建任务示例

请求体：

```json
{
  "input_text": "FastAPI 可以用 BackgroundTasks 提交后台任务。接口先返回 task_id，任务完成后再通过查询接口读取结果。"
}
```

提交后你会先拿到：

```json
{
  "task_id": 1,
  "status": "pending",
  "status_url": "/summary-tasks/1"
}
```

然后访问：

```text
GET /summary-tasks/1
```

观察状态从 `pending` 或 `running` 变成 `succeeded`。

## 故意触发失败

提交包含 `FAIL_TASK` 的文本：

```json
{
  "input_text": "FAIL_TASK"
}
```

任务会进入 `failed` 状态，并保存错误信息。

## 本课练习

1. 对比同步接口和后台任务：说明为什么 `POST /summary-tasks` 不能直接返回最终摘要。
2. 提交一个正常任务和一个包含 `FAIL_TASK` 的失败任务，记录两条任务的状态变化。
3. 给任务增加 `task_type` 字段，思考以后同一张表如何支持摘要、翻译、文档解析等不同任务。
4. 给 `GET /summary-tasks` 增加 `status` 查询参数，只查询 `pending`、`running`、`succeeded` 或 `failed` 的任务。

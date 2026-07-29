# 逐段讲解

这一节学习后台任务。

## 为什么需要后台任务

普通接口是同步的：

```text
请求进来 -> 处理完成 -> 返回结果
```

如果处理只需要几十毫秒，这没问题。

但 AI 应用经常有慢任务：

- 解析文件
- 生成摘要
- 调用模型
- 批量处理数据

如果这些都放在一个 HTTP 请求里，用户会一直等待，接口也更容易超时。

后台任务的思路是：

```text
请求进来 -> 创建任务 -> 返回 task_id -> 后台处理 -> 查询结果
```

## 文件分工

`main.py`

接口层，负责：

- 创建任务
- 查询任务
- 注册后台任务

`db.py`

数据层，负责：

- 创建任务记录
- 更新任务状态
- 查询任务结果

`worker.py`

后台任务处理器，负责：

- 把任务改成 running
- 调用 provider 生成摘要
- 成功时保存 result
- 失败时保存 error

`provider.py`

模型调用层，负责：

- mock 摘要
- DeepSeek 摘要

## 状态流转

```text
pending -> running -> succeeded
pending -> running -> failed
```

每个状态的意思：

- `pending`：任务已创建，还没开始处理。
- `running`：后台正在处理。
- `succeeded`：任务成功完成，可以看 result。
- `failed`：任务失败，可以看 error。

## 关键代码

```python
background_tasks.add_task(
    process_summary_task,
    task["id"],
    payload.input_text,
)
```

这表示 FastAPI 响应当前请求后，会在后台执行：

```python
process_summary_task(task_id, input_text)
```

你可以类比成 Java 里把任务交给一个异步执行器。

## 这个模块的限制

FastAPI 的 `BackgroundTasks` 适合学习和轻量任务。

正式生产项目如果任务很重，通常会使用：

- Celery
- RQ
- Dramatiq
- Redis 队列
- 云厂商任务队列

本模块先不引入这些，是为了先学会核心概念：

```text
任务入库 -> 后台处理 -> 状态查询 -> 结果保存
```

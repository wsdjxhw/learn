# 短期状态代码讲解

这份文档按代码执行顺序解释模块。建议先跑通 README 里的接口，再回来看这里。

## 1. `.env.example` 和 `settings.py`

`.env.example` 提供三类配置：

- `MODEL_MODE`：决定使用 mock 还是真实 DeepSeek。
- `DEEPSEEK_*`：真实模型调用配置。
- `DATABASE_URL`：数据库连接地址。

`settings.py` 用 `load_dotenv()` 读取 `.env`。`get_settings()` 上加了 `@lru_cache`，表示配置对象只创建一次。

这里的重点不是语法炫技，而是让配置和业务代码分开。以后切换模型、数据库或部署环境时，不应该到处改业务函数。

## 2. `database.py`

`database.py` 负责创建 SQLAlchemy 基础设施：

- `Base`：所有 ORM Model 的父类。
- `engine`：数据库连接引擎。
- `SessionLocal`：创建数据库会话的工厂。
- `init_db()`：启动时创建表。
- `get_db()`：给 FastAPI 接口注入数据库会话。

`get_db()` 里用了 `yield`：

```python
db = SessionLocal()
try:
    yield db
finally:
    db.close()
```

这表示接口执行前创建 `db`，接口执行后无论成功失败都关闭连接。

Java 类比：`db: Session = Depends(get_db)` 类似框架自动注入一个数据库操作对象，但 Python/FastAPI 写法更显式。

## 3. `models.py`

`models.py` 定义两张表。

`AgentRun` 表示一次 Agent 执行：

- `run_id`：唯一标识。
- `user_goal`：用户目标。
- `status`：pending/running/succeeded/failed。
- `final_answer`：最终回答。
- `error`：run 级错误。
- `next_step_index`：恢复执行时下一步从哪里开始。

`AgentStep` 表示一次执行里的步骤：

- `step_index`：第几步。
- `step_type`：plan、tool_call、final_answer、error。
- `name`：具体步骤名。
- `input_json`：这一步输入。
- `output_json`：这一步输出。
- `error`：这一步错误。

初学者要特别注意：ORM Model 是数据库表结构，不是接口请求体。接口请求体在 `schemas.py`。

## 4. `schemas.py`

`schemas.py` 定义 DTO：

- `RunCreateRequest`：创建 run 的请求体。
- `RunResumeRequest`：恢复 run 的请求体。
- `StepResponse`：返回给前端看的 step。
- `RunResponse`：返回给前端看的完整 run。
- `RunListItem`：列表页使用的简化 run 信息。

为什么不直接返回 ORM 对象？

因为数据库字段经常不是前端想要的最终结构。比如 `input_json` 在数据库里是字符串，但接口应该返回 dict。DTO 可以把后端内部结构和接口契约隔开。

## 5. `state_store.py`

`state_store.py` 是短期状态读写层。

它负责：

- `create_run()`：创建一条 pending run。
- `get_run()`：按 `run_id` 查询 run。
- `list_runs()`：列出最近 run。
- `mark_run_status()`：更新 run 状态。
- `add_step()`：写入一步执行记录。
- `set_final_answer()`：保存最终回答并把 run 标记为 succeeded。
- `to_run_response()`：把 ORM 对象转成接口 DTO。

`db.add()`、`db.commit()`、`db.refresh()` 是 SQLAlchemy 常见三连：

- `db.add()`：告诉数据库会话要保存这个对象。
- `db.commit()`：真正提交到数据库。
- `db.refresh()`：从数据库重新读取对象，拿到数据库生成或更新后的值。

`add_step()` 里有一个关键参数：

```python
advance_next_step: bool = True
```

普通成功 step 会推进 `next_step_index`。失败记录不会推进。否则恢复执行时会跳过真正失败的业务步骤。

这就是状态设计里的细节：错误日志和业务进度不是同一个概念。

## 6. `tools.py`

`tools.py` 里有两个教学工具：

- `search_refund_policy()`：模拟检索售后规则。
- `calculate_refund_amount()`：模拟计算退款金额。

它们都返回 dict。这样后续 step 可以把工具输出原样保存到 `output_json`。

真实项目里工具可能访问 RAG、订单系统、CRM、工单系统或支付系统。但学习短期状态时，工具本身不宜复杂，否则会遮住本模块重点。

## 7. `provider.py`

`provider.py` 负责生成最终回答。

mock 模式直接根据工具结果拼接稳定回答。这样没有 API Key 也能跑完整链路。

DeepSeek 模式使用：

```python
OpenAI(api_key=..., base_url=...)
```

这说明 DeepSeek 提供 OpenAI 兼容接口，可以用 `openai` Python 包调用。

本模块只在最后一步调用模型。原因是当前学习重点是短期状态，而不是让模型决定每个步骤。等后续工具工程、RAG 智能体和数据库智能体模块，会逐步让模型承担更多决策。

## 8. `agent_runner.py`

`agent_runner.py` 是执行链路核心。

主函数是：

```python
run_agent_background(run_id, simulate_failure_at_step, delay_seconds)
```

它会：

1. 重新创建数据库 session。
2. 查询 run。
3. 把 run 状态改为 running。
4. 写入 plan step。
5. 调用规则检索工具并写入 step。
6. 调用退款计算工具并写入 step。
7. 调用模型生成最终回答并写入 step。
8. 把 run 标记为 succeeded。

为什么后台任务里要重新创建 `SessionLocal()`？

因为接口函数里的数据库 session 属于当前请求。接口返回后，它会被关闭。后台任务继续执行时必须有自己的 session。

`simulate_failure_at_step` 是教学故障开关。它让你不用真的破坏代码，就能观察失败现场如何保存。

## 9. `main.py`

`main.py` 提供接口：

- `GET /health`：查看模块状态。
- `POST /agent/runs`：创建 run，并启动后台执行。
- `GET /agent/runs`：查看 run 列表。
- `GET /agent/runs/{run_id}`：查看某个 run 的完整状态和 steps。
- `POST /agent/runs/{run_id}/resume`：恢复失败 run。

`POST /agent/runs` 里有三个重要参数来源：

- `payload`：请求体，由 FastAPI 根据 `RunCreateRequest` 创建。
- `background_tasks`：FastAPI 注入的后台任务对象。
- `db`：通过 `Depends(get_db)` 注入的数据库会话。

`background_tasks.add_task()` 的作用是把函数安排到接口返回后执行。用户不用一直等到 Agent 完成，前端可以用 `run_id` 轮询状态。

## 10. 完整链路

一次成功请求的链路是：

```text
POST /agent/runs
-> create_run() 写入 pending run
-> background_tasks.add_task()
-> run_agent_background()
-> mark_run_status(running)
-> add_step(plan)
-> search_refund_policy()
-> add_step(tool_call)
-> calculate_refund_amount()
-> add_step(tool_call)
-> generate_final_answer()
-> add_step(final_answer)
-> set_final_answer(succeeded)
```

查询链路是：

```text
GET /agent/runs/{run_id}
-> get_run()
-> to_run_response()
-> 返回 run + steps
```

恢复链路是：

```text
POST /agent/runs/{run_id}/resume
-> 检查 run 是否 failed
-> 清除错误
-> 重新提交后台任务
-> 根据 next_step_index 继续执行
```

这就是本模块要掌握的核心：Agent 不是一次函数调用，而是一条可保存、可查询、可恢复的执行流。

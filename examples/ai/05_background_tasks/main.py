from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from db import create_summary_task, get_summary_task, init_db, list_summary_tasks
from provider import get_model_name, get_provider_name
from worker import process_summary_task

app = FastAPI(title="AI Background Tasks")


class SummaryTaskCreate(BaseModel):
    # 请求 DTO：客户端提交一段文本，让后台任务生成摘要。
    # 类比 Java 里的 CreateSummaryTaskRequest。
    input_text: str


@app.on_event("startup")
def startup() -> None:
    # 服务启动时创建 summary_tasks 表。
    init_db()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
    }


@app.post("/summary-tasks")
def create_task(
    payload: SummaryTaskCreate,
    background_tasks: BackgroundTasks,
) -> dict:
    # 这个接口不会等待摘要生成完成。
    # 它只创建任务、返回 task_id，然后让 FastAPI 在后台执行 worker。
    if not payload.input_text.strip():
        raise HTTPException(status_code=400, detail="input_text is empty")

    task = create_summary_task(input_text=payload.input_text)

    # BackgroundTasks 是 FastAPI 提供的后台任务工具。
    # add_task 的第一个参数是要执行的函数，后面是传给这个函数的参数。
    background_tasks.add_task(
        process_summary_task,
        task["id"],
        payload.input_text,
    )

    return {
        "task_id": task["id"],
        "status": task["status"],
        "status_url": f"/summary-tasks/{task['id']}",
    }


@app.get("/summary-tasks/{task_id}")
def get_task(task_id: int) -> dict:
    # 通过 task_id 查询任务状态。
    # 前端可以每隔几秒请求一次这个接口，实现“轮询”。
    task = get_summary_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/summary-tasks")
def get_tasks() -> dict:
    # 查看所有任务，方便观察多个任务的状态变化。
    return {"items": list_summary_tasks()}

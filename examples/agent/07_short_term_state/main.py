from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from agent_runner import run_agent_background
from database import get_db, init_db
from schemas import RunCreateRequest, RunResumeRequest
from settings import get_settings
from state_store import add_step, create_run, get_run, list_runs, mark_run_status, to_run_response


# main.py 是 Web API 层。
# Java 类比：可以理解成 Controller，只负责接收请求、调用业务函数、返回 DTO。
app = FastAPI(title="Short Term Agent State Teaching Demo")


@app.on_event("startup")
def on_startup() -> None:
    # 服务启动时创建数据库表。
    # 本模块重点是短期状态，不让初学者先卡在迁移命令上；正式项目会用 Alembic。
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "module": "07_short_term_state",
        "model_mode": settings.model_mode,
        "database_url": settings.database_url,
        "has_deepseek_api_key": bool(settings.deepseek_api_key),
    }


@app.post("/agent/runs")
def create_agent_run(
    payload: RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # payload 来自请求体。
    # background_tasks 是 FastAPI 注入的后台任务对象，可以在接口返回后继续执行函数。
    # db: Session = Depends(get_db) 表示 FastAPI 自动注入数据库会话。
    run = create_run(db, payload)
    background_tasks.add_task(
        run_agent_background,
        run.run_id,
        payload.simulate_failure_at_step,
        payload.delay_seconds,
    )
    return {
        "message": "Agent run 已创建。请用 run_id 查询状态。",
        "run_id": run.run_id,
        "status": run.status,
        "query_url": f"/agent/runs/{run.run_id}",
    }


@app.get("/agent/runs")
def list_agent_runs(db: Session = Depends(get_db)) -> dict[str, Any]:
    # 列表接口方便刷新页面后找回最近执行记录。
    return {"runs": [item.model_dump() for item in list_runs(db)]}


@app.get("/agent/runs/{run_id}")
def get_agent_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    # run_id 是路径参数。
    # FastAPI 会从 /agent/runs/{run_id} 的 URL 里取出它。
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_id 不存在。")
    return {"run": to_run_response(run).model_dump()}


@app.post("/agent/runs/{run_id}/resume")
def resume_agent_run(
    run_id: str,
    payload: RunResumeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # resume 用来演示短期状态的恢复价值。
    # 如果前一次执行在第 2 步失败，run.next_step_index 会指向下一次应该执行的位置。
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_id 不存在。")
    if run.status != "failed":
        raise HTTPException(status_code=400, detail="只有 failed 的 run 才需要恢复执行。")

    if payload.clear_failure:
        mark_run_status(db, run, "pending", error=None)

    background_tasks.add_task(run_agent_background, run.run_id, None, payload.delay_seconds)
    return {
        "message": "Agent run 已提交恢复执行。",
        "run_id": run.run_id,
        "status": "pending",
        "query_url": f"/agent/runs/{run.run_id}",
    }

@app.post("/agent/runs/{run_id}/cancel")
def cancel_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # 练习二：只有 pending 或 running 的 run 可以取消。
    # 取消不是把记录删掉，而是写入一条 step 说明是谁、什么时候取消的，
    # 再把 run 标记为失败。这样现场仍然可查。
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_id 不存在。")
    if run.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="只有 pending 或 running 的 run 可以取消。")

    # add_step 会处理 JSON 序列化、commit、next_step_index 管理。
    # advance_next_step=False 表示取消不推进进度索引，因为执行被中止了。
    add_step(
        db,
        run,
        step_type="error",
        name="agent_cancelled",
        input_data={"run_id": run_id},
        output_data={},
        status="failed",
        error="用户取消了本次执行。",
        advance_next_step=False,
    )
    mark_run_status(db, run, "failed", error="用户取消")

    return {
        "message": "Agent run 已取消。",
        "run_id": run.run_id,
        "status": run.status,
        "query_url": f"/agent/runs/{run.run_id}",
    }
    
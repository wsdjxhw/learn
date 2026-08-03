import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AgentRun, AgentStep
from schemas import RunCreateRequest, RunListItem, RunResponse, StepResponse


def create_run(db: Session, payload: RunCreateRequest) -> AgentRun:
    # uuid4() 生成不容易重复的 run_id。
    # run_id 是前端后续查询状态的核心标识，类似后台任务模块里的 task_id。
    run = AgentRun(
        run_id=str(uuid4()),
        user_goal=payload.user_goal,
        status="pending",
        next_step_index=1,
        updated_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: str) -> AgentRun | None:
    # select() 是 SQLAlchemy 2.x 推荐查询写法。
    # scalar_one_or_none() 表示：查到一条就返回对象，查不到就返回 None。
    return db.execute(select(AgentRun).where(AgentRun.run_id == run_id)).scalar_one_or_none()


def list_runs(db: Session) -> list[RunListItem]:
    result = db.execute(select(AgentRun).order_by(AgentRun.created_at.desc())).scalars().all()
    items: list[RunListItem] = []
    for run in result:
        items.append(
            RunListItem(
                run_id=run.run_id,
                user_goal=run.user_goal,
                status=run.status,
                step_count=len(run.steps),
                created_at=run.created_at.isoformat(),
                updated_at=run.updated_at.isoformat(),
            )
        )
    return items


def mark_run_status(db: Session, run: AgentRun, status: str, error: str | None = None) -> None:
    run.status = status
    run.error = error
    run.updated_at = datetime.utcnow()
    db.add(run)
    db.commit()


def add_step(
    db: Session,
    run: AgentRun,
    step_type: str,
    name: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any] | None = None,
    status: str = "succeeded",
    error: str | None = None,
    advance_next_step: bool = True,
) -> AgentStep:
    # input_data / output_data 用 JSON 字符串保存。
    # 这是为了让 SQLite、PostgreSQL 都能跑通；生产 PostgreSQL 可以换成 JSONB 字段。
    now = datetime.utcnow()
    step = AgentStep(
        run_id=run.run_id,
        step_index=run.next_step_index,
        step_type=step_type,
        name=name,
        status=status,
        input_json=json.dumps(input_data, ensure_ascii=False),
        output_json=json.dumps(output_data or {}, ensure_ascii=False),
        error=error,
        started_at=now,
        finished_at=now,
    )
    db.add(step)
    if advance_next_step:
        run.next_step_index += 1
    run.updated_at = now
    db.add(run)
    db.commit()
    db.refresh(step)
    db.refresh(run)
    return step


def set_final_answer(db: Session, run: AgentRun, final_answer: str) -> None:
    run.status = "succeeded"
    run.final_answer = final_answer
    run.error = None
    run.updated_at = datetime.utcnow()
    db.add(run)
    db.commit()


def to_run_response(run: AgentRun) -> RunResponse:
    # ORM 对象不能直接当接口响应。
    # 这里显式转成 Pydantic DTO，前端拿到的结构会更稳定。
    steps: list[StepResponse] = []
    for step in run.steps:
        steps.append(
            StepResponse(
                step_index=step.step_index,
                step_type=step.step_type,
                name=step.name,
                status=step.status,
                input=json.loads(step.input_json),
                output=json.loads(step.output_json),
                error=step.error,
                started_at=step.started_at.isoformat(),
                finished_at=step.finished_at.isoformat() if step.finished_at else None,
            )
        )

    return RunResponse(
        run_id=run.run_id,
        user_goal=run.user_goal,
        status=run.status,
        final_answer=run.final_answer,
        error=run.error,
        next_step_index=run.next_step_index,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
        steps=steps,
    )

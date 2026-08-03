import time

from sqlalchemy.orm import Session

from database import SessionLocal
from provider import generate_final_answer
from state_store import add_step, get_run, mark_run_status, set_final_answer
from tools import calculate_refund_amount, search_refund_policy


def _maybe_fail(current_step: int, simulate_failure_at_step: int | None) -> None:
    # 这个函数专门用于教学演示失败现场。
    # 如果请求里传 simulate_failure_at_step=2，Agent 会在第 2 步失败，前面已完成的 step 仍然保存在数据库。
    if simulate_failure_at_step == current_step:
        raise RuntimeError(f"教学模拟失败：第 {current_step} 步执行失败。")


def run_agent_background(
    run_id: str,
    simulate_failure_at_step: int | None = None,
    delay_seconds: float = 0.3,
) -> None:
    # 后台任务不能复用接口函数里的 db session。
    # 因为接口已经返回后，原来的 session 可能被关闭，所以这里重新创建一个 SessionLocal。
    db: Session = SessionLocal()
    try:
        run = get_run(db, run_id)
        if run is None:
            return

        mark_run_status(db, run, "running")
        policy: dict | None = None
        refund: dict | None = None

        # next_step_index 让失败后的恢复成为可能。
        # 如果第 2 步失败，恢复时会从第 2 步重新执行，而不是重复写第 1 步。
        if run.next_step_index <= 1:
            _maybe_fail(1, simulate_failure_at_step)
            add_step(
                db,
                run,
                step_type="plan",
                name="拆解用户目标",
                input_data={"user_goal": run.user_goal},
                output_data={"plan": ["检索退款规则", "计算退款金额", "生成最终回答"]},
            )
            time.sleep(delay_seconds)

        if run.next_step_index <= 2:
            _maybe_fail(2, simulate_failure_at_step)
            policy = search_refund_policy(run.user_goal)
            add_step(
                db,
                run,
                step_type="tool_call",
                name="search_refund_policy",
                input_data={"query": run.user_goal},
                output_data=policy,
            )
            time.sleep(delay_seconds)
        else:
            # 如果是恢复执行，需要从已保存的 step 里重建后续步骤依赖的数据。
            policy_step = next(step for step in run.steps if step.name == "search_refund_policy")
            import json

            policy = json.loads(policy_step.output_json)

        if run.next_step_index <= 3:
            _maybe_fail(3, simulate_failure_at_step)
            refund = calculate_refund_amount(order_amount=240, is_damaged=True)
            add_step(
                db,
                run,
                step_type="tool_call",
                name="calculate_refund_amount",
                input_data={"order_amount": 240, "is_damaged": True},
                output_data=refund,
            )
            time.sleep(delay_seconds)
        else:
            refund_step = next(step for step in run.steps if step.name == "calculate_refund_amount")
            import json

            refund = json.loads(refund_step.output_json)

        if run.next_step_index <= 4:
            _maybe_fail(4, simulate_failure_at_step)
            answer = generate_final_answer(run.user_goal, policy, refund)
            add_step(
                db,
                run,
                step_type="final_answer",
                name="generate_final_answer",
                input_data={"policy": policy, "refund": refund},
                output_data={"answer": answer},
            )
            set_final_answer(db, run, answer)
    except Exception as exc:
        # 失败时也要写入 step。
        # 这正是短期状态管理的价值：接口失败不是只返回 500，而是留下可以排查的执行现场。
        latest_run = get_run(db, run_id)
        if latest_run is not None:
            add_step(
                db,
                latest_run,
                step_type="error",
                name="agent_execution_error",
                input_data={"run_id": run_id},
                output_data={},
                status="failed",
                error=str(exc),
                advance_next_step=False,
            )
            mark_run_status(db, latest_run, "failed", error=str(exc))
    finally:
        db.close()

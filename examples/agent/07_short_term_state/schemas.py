from typing import Literal

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    # 这是创建 Agent run 的请求 DTO。
    # Java 类比：BaseModel 更像 Controller 入参 DTO，不是数据库 Entity。
    user_goal: str = Field(
        min_length=1,
        description="用户希望 Agent 完成的目标，例如：帮我判断订单是否可以退款。",
    )
    simulate_failure_at_step: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description="教学用故障开关。传 2 或 3 可以观察失败后 steps 如何被保存。",
    )
    delay_seconds: float = Field(
        default=0.3,
        ge=0,
        le=3,
        description="每一步之间等待几秒。调大后更容易用查询接口看到 running 中间状态。",
    )


class RunResumeRequest(BaseModel):
    # resume 不是重新创建任务，而是基于已有 run 继续执行。
    # 真实项目里常用于人工修复参数、工具恢复、网络失败后重试。
    clear_failure: bool = Field(
        default=True,
        description="是否清除上次失败原因。一般恢复执行时应该清除，否则页面会一直显示旧错误。",
    )
    delay_seconds: float = Field(
        default=0.3,
        ge=0,
        le=3,
        description="恢复执行时每一步之间等待几秒。",
    )


class StepResponse(BaseModel):
    # StepResponse 是返回给前端看的 step DTO。
    # 注意它和 ORM AgentStep 不同：ORM 负责入库，DTO 负责接口返回结构。
    step_index: int
    step_type: str
    name: str
    status: str
    input: dict
    output: dict
    error: str | None
    started_at: str
    finished_at: str | None
    duration_ms: int | None


class RunResponse(BaseModel):
    run_id: str
    user_goal: str
    status: Literal["pending", "running", "succeeded", "failed"]
    final_answer: str | None
    error: str | None
    next_step_index: int
    created_at: str
    updated_at: str
    steps: list[StepResponse]


class RunListItem(BaseModel):
    run_id: str
    user_goal: str
    status: str
    step_count: int
    created_at: str
    updated_at: str

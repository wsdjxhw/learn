from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from orchestrator import run_orchestration
from planner import build_plan
from tools import list_tool_schemas


# main.py 负责 Web API 层。
# Java 类比：可以把它理解成 Controller，只接收 HTTP 请求、调用业务函数、返回 HTTP 响应。
# 本模块真正要学的是“多工具编排”，所以编排逻辑放在 orchestrator.py，工具实现放在 tools.py。
app = FastAPI(title="Multi Tool Orchestration Teaching Demo")


class AgentCaseRequest(BaseModel):
    # BaseModel 类似 Java 里的请求 DTO。
    # FastAPI 会把请求体 JSON 转成 AgentCaseRequest 对象，并自动做基础类型校验。
    goal: str = Field(
        default="帮客户判断退款金额，并生成一段客服回复",
        description="用户交给 Agent 的目标。教学版 planner 会根据这个目标组织工具步骤。",
    )
    customer_name: str = Field(default="小王", description="客户姓名，用于最终生成客服回复。")
    order_amount: float = Field(default=240, ge=0, description="订单金额，单位是元。")
    days_since_purchase: int = Field(default=5, ge=0, description="客户购买后经过了多少天。")
    item_problem: str = Field(
        default="破损",
        description="商品问题，例如：破损、不喜欢、未收到、其他。",
    )
    policy_keyword: str = Field(
        default="退款",
        description="要检索的制度关键词。改成未知关键词可以观察工具失败后的流程变化。",
    )
    stop_on_error: bool = Field(
        default=False,
        description="工具失败时是否立刻停止。默认继续，让你看到依赖步骤如何被跳过。",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    # 本模块不调用真实外部模型，使用教学版 planner 模拟“模型规划步骤”。
    # 这样学习重点会落在工具编排和数据流上，而不是 key、网络和模型随机性上。
    return {
        "status": "ok",
        "module": "03_multi_tool_orchestration",
        "planner": "teaching_mock_planner",
        "tool_count": len(list_tool_schemas()),
    }


@app.get("/tools")
def tools() -> dict[str, Any]:
    # 查看工具清单。
    # 学多工具编排前，先确认 Agent 有哪些可用动作。
    return {
        "tools": list_tool_schemas(),
    }


@app.post("/agent/plan")
def preview_plan(payload: AgentCaseRequest) -> dict[str, Any]:
    # 只生成计划，不执行工具。
    # 这个接口适合先观察“一个用户目标会被拆成哪些工具动作”。
    case = payload.model_dump()
    return {
        "request": case,
        "plan": build_plan(case),
    }


@app.post("/agent/run")
def run_agent_api(payload: AgentCaseRequest) -> dict[str, Any]:
    # 本模块的核心接口。
    # 输入来自请求体；处理过程在 orchestrator.py；输出会包含 steps，方便学习者追踪每一步。
    case = payload.model_dump()
    result = run_orchestration(case=case)
    return {
        "request": case,
        "result": result,
    }

from typing import Any

from fastapi import FastAPI

from agent import run_structured_agent
from schemas import RefundDecision, StructuredCompareRequest, StructuredRunRequest
from settings import get_settings


# main.py 负责 Web API 层。
# Java 类比：可以把它理解成 Controller。
# 本模块的重点是“接口层接收请求 -> Agent 层拿模型原始输出 -> parser 层解析和校验 -> 返回稳定结构”。
app = FastAPI(title="Structured Output Teaching Demo")


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "module": "05_structured_output",
        "model_mode": settings.model_mode,
        "has_deepseek_api_key": bool(settings.deepseek_api_key),
        "schema_name": "RefundDecision",
    }


@app.get("/output-schema")
def output_schema() -> dict[str, Any]:
    # Pydantic 可以把 BaseModel 转成 JSON Schema。
    # 这份 schema 既可以给模型看，也可以给前端、测试和接口文档看。
    return {
        "schema": RefundDecision.model_json_schema(),
    }


@app.post("/agent/run")
def run_agent_api(payload: StructuredRunRequest) -> dict[str, Any]:
    # payload 是 FastAPI 根据请求体自动创建的对象。
    # model_dump() 把 Pydantic 对象转回普通 dict，方便传给 Agent 层。
    case = payload.model_dump()
    result = run_structured_agent(case)
    return {
        "request": case,
        "result": result,
    }


@app.post("/agent/compare")
def compare_scenarios(payload: StructuredCompareRequest) -> dict[str, Any]:
    # compare 接口用来批量观察各种模型坏输出：
    # - 语法坏了：broken_json。
    # - 字段缺失：missing_field。
    # - 类型错误：wrong_type。
    # - 枚举非法：invalid_enum。
    #
    # 这比只看一个成功案例更接近真实工程排错。
    results: list[dict[str, Any]] = []
    for scenario in payload.scenarios:
        case = payload.model_dump()
        case["mock_scenario"] = scenario
        result = run_structured_agent(case)
        results.append(
            {
                "scenario": scenario,
                "status": result["status"],
                "retry_used": result["retry_used"],
                "decision": result["decision"],
                "attempts": result["attempts"],
            }
        )

    return {
        "request": payload.model_dump(),
        "results": results,
    }

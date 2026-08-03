from typing import Any

from fastapi import FastAPI

from agent import run_context_agent
from context_builder import build_context
from provider import generate_model_answer
from sample_data import list_demo_cases
from schemas import ContextBuildRequest
from settings import get_settings


# main.py 是 Web API 层。
# Java 类比：可以理解成 Controller。
# 本模块把“预览上下文”和“真正调用模型”拆成两个接口，方便初学者先看清模型输入。
app = FastAPI(title="Context Engineering Teaching Demo")


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "module": "06_context_engineering",
        "model_mode": settings.model_mode,
        "has_deepseek_api_key": bool(settings.deepseek_api_key),
    }


@app.get("/demo-cases")
def demo_cases() -> dict[str, Any]:
    # 这个接口只返回可用教学场景，方便在 /docs 里复制 context_scenario。
    return {"cases": list_demo_cases()}


@app.post("/context/preview")
def preview_context(payload: ContextBuildRequest) -> dict[str, Any]:
    # payload 是 FastAPI 从请求体创建的 Pydantic 对象。
    # 这个接口不会调用模型，只展示 build_context() 的结果。
    context = build_context(payload)
    return {
        "request": payload.model_dump(),
        "context": context.model_dump(),
    }


@app.post("/agent/run")
def run_agent_api(payload: ContextBuildRequest) -> dict[str, Any]:
    # model_dump() 把 Pydantic 对象转成普通 dict。
    # 这样 agent.py 不依赖 FastAPI，也方便以后写单元测试。
    return {
        "request": payload.model_dump(),
        "result": run_context_agent(payload.model_dump()),
    }


@app.post("/agent/compare-noisy-context")
def compare_noisy_context(payload: ContextBuildRequest) -> dict[str, Any]:
    # 这个接口专门演示“上下文太多反而干扰回答”。
    # strict_request 会过滤低相关 RAG。
    # loose_request 会故意放入低相关 RAG，观察 mock 回答如何被干扰。
    strict_request = payload.model_copy(
        update={
            "context_scenario": "noisy_rag",
            "include_low_relevance_sources": False,
            "rag_min_relevance": 0.55,
        }
    )
    loose_request = payload.model_copy(
        update={
            "context_scenario": "noisy_rag",
            "include_low_relevance_sources": True,
            "rag_min_relevance": 0,
        }
    )

    strict_context = build_context(strict_request)
    loose_context = build_context(loose_request)

    return {
        "strict": {
            "request": strict_request.model_dump(),
            "answer": generate_model_answer(strict_context),
            "context": strict_context.model_dump(),
        },
        "loose": {
            "request": loose_request.model_dump(),
            "answer": generate_model_answer(loose_context),
            "context": loose_context.model_dump(),
        },
        "lesson": "RAG source 进入上下文前必须过滤相关性。不是资料越多越好，无关资料会改变模型注意力。",
    }

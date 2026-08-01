from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from provider import (
    decide_next_action,
    generate_final_answer,
    get_api_key,
    get_model_name,
    get_provider_name,
)
from tools import list_tool_schemas, run_tool

# main.py 负责 Web API 层。
# Java 类比：可以把它理解成 Controller，只负责接收 HTTP 请求、调用业务函数、返回 HTTP 响应。
# 工具定义放在 tools.py，模型决策放在 provider.py，这样初学者能清楚看到分层。
app = FastAPI(title="Agent Tool Calling Teaching Demo")


class ChatRequest(BaseModel):
    # BaseModel 类似 Java 里的请求 DTO。
    # FastAPI 会把请求体 JSON 自动解析成 ChatRequest 对象。
    message: str = Field(..., description="用户输入的问题")
    system_prompt: str = Field(
        default="你是一个会谨慎使用工具的编程学习助手。",
        description="给模型的系统提示词",
    )
    allow_tool: bool = Field(
        default=True,
        description="是否允许本次请求调用工具，用来对比有工具和无工具的差异",
    )


class ToolRunRequest(BaseModel):
    # 这个 DTO 用于手动测试工具。
    # arguments 用 dict，是因为不同工具需要的参数不同：
    # get_weather 需要 city，calculate_order_total 需要 item_price 和 quantity。
    tool_name: str = Field(..., description="工具名称")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="工具参数，结构取决于具体工具 schema",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    # 这个接口用于确认服务是否启动成功，以及当前是 mock 模式还是真实 DeepSeek 模式。
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
        "has_api_key": bool(get_api_key()),
        "tool_count": len(list_tool_schemas()),
    }


@app.get("/tools")
def tools() -> dict[str, Any]:
    # 这个接口让学习者直接看到“模型能使用哪些工具”。
    # 真实模型调用时，provider.py 也会把同一份 schema 传给模型。
    return {
        "tools": list_tool_schemas(),
    }


@app.post("/tool/run")
def run_tool_manually(payload: ToolRunRequest) -> dict[str, Any]:
    # 这个接口绕过模型，直接执行工具。
    # 学习工具调用时，先手动验证工具输入输出，会比一开始就看模型决策更清楚。
    tool_output = run_tool(
        tool_name=payload.tool_name,
        arguments=payload.arguments,
    )
    return {
        "request": payload.model_dump(),
        "tool_output": tool_output,
    }


@app.post("/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    # 这是本模块的核心接口。
    # 它只演示“一次用户请求里最多调用一个工具”：
    # 1. 用户输入问题；
    # 2. provider 决定直接回答还是调用工具；
    # 3. 如果需要工具，main.py 执行工具；
    # 4. provider 把工具结果整理成最终回答。
    steps: list[dict[str, Any]] = [
        {
            "step": "user_input",
            "message": payload.message,
        }
    ]

    decision = decide_next_action(
        user_message=payload.message,
        system_prompt=payload.system_prompt,
        allow_tool=payload.allow_tool,
    )
    steps.append(
        {
            "step": "model_decision",
            "decision": decision,
        }
    )

    if decision["type"] == "answer":
        # 模型如果直接回答，就没有工具执行阶段。
        return {
            "reply": decision["answer"],
            "used_tool": False,
            "provider": get_provider_name(),
            "model": get_model_name(),
            "steps": steps,
        }

    tool_output = run_tool(
        tool_name=decision["tool_name"],
        arguments=decision["arguments"],
    )
    steps.append(
        {
            "step": "tool_execution",
            "tool_output": tool_output,
        }
    )

    reply = generate_final_answer(
        user_message=payload.message,
        system_prompt=payload.system_prompt,
        decision=decision,
        tool_output=tool_output,
    )
    steps.append(
        {
            "step": "final_answer",
            "reply": reply,
        }
    )

    return {
        "reply": reply,
        "used_tool": True,
        "tool_name": decision["tool_name"],
        "tool_output": tool_output,
        "provider": get_provider_name(),
        "model": get_model_name(),
        "steps": steps,
    }

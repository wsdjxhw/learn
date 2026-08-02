from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent_loop import run_agent
from provider import get_api_key, get_default_max_steps, get_model_name, get_provider_name
from tools import list_tool_schemas


# main.py 负责 Web API 层。
# Java 类比：可以把它理解成 Controller，只接收 HTTP 请求、调用业务函数、返回 HTTP 响应。
# Agent 循环放在 agent_loop.py，模型决策和 DeepSeek 调用放在 provider.py，工具执行放在 tools.py。
app = FastAPI(title="Minimal Agent Loop Teaching Demo")


class AgentRunRequest(BaseModel):
    # BaseModel 类似 Java 里的请求 DTO。
    # FastAPI 会把请求体 JSON 自动转换成 AgentRunRequest 对象。
    message: str = Field(..., description="用户给 Agent 的目标")
    max_steps: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="最多允许 Agent 执行多少轮。为空时读取 .env 或默认值。",
    )
    allow_tools: bool = Field(
        default=True,
        description="是否允许调用工具。关闭后可对比普通回答和 Agent Loop 的差异。",
    )
    system_prompt: str = Field(
        default=(
            "你是一个教学版 Agent。你需要围绕用户目标逐步工作："
            "如果需要外部信息，就调用工具；如果 observation 已经足够，就给出最终回答。"
            "不要重复调用已经成功完成且结果足够的工具。"
        ),
        description="给真实模型的系统提示词。mock 模式下主要用于保持接口结构一致。",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    # 用于确认服务启动成功，以及当前是真实 DeepSeek 模式还是 mock 模式。
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
        "has_api_key": bool(get_api_key()),
        "default_max_steps": get_default_max_steps(),
        "tool_count": len(list_tool_schemas()),
    }


@app.get("/tools")
def tools() -> dict[str, Any]:
    # 查看工具清单。
    # 学 Agent Loop 前先确认工具有哪些，后面看 steps 时才知道每次 action 在调用什么。
    return {
        "tools": list_tool_schemas(),
    }


@app.post("/agent/run")
def run_agent_api(payload: AgentRunRequest) -> dict[str, Any]:
    # 这是本模块的核心接口。
    # 请求体里的 message 来自用户输入；max_steps 和 allow_tools 用来控制 Agent 执行边界。
    max_steps = payload.max_steps or get_default_max_steps()
    result = run_agent(
        user_message=payload.message,
        system_prompt=payload.system_prompt,
        max_steps=max_steps,
        allow_tools=payload.allow_tools,
    )
    return {
        "request": payload.model_dump(),
        "effective_max_steps": max_steps,
        "provider": get_provider_name(),
        "model": get_model_name(),
        "result": result,
    }

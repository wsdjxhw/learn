from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent import basic_chat_reply, run_minimal_agent

# main.py 是 Web API 入口。
# Java 类比：这里像 Controller，负责把 HTTP 请求转给 agent.py 处理。
app = FastAPI(title="What Is Agent Teaching Demo")


class ChatRequest(BaseModel):
    # BaseModel 类似 Java 的请求 DTO。
    # FastAPI 会把请求体 JSON 自动转成 ChatRequest 对象。
    message: str = Field(..., description="用户输入的一句话")


class AgentRunRequest(BaseModel):
    # goal 表示用户希望 Agent 帮忙完成的目标。
    # 这里故意不用 message，是为了强调 Agent 面向“目标”，不只是面向“一问一答”。
    goal: str = Field(..., description="希望 Agent 处理的目标")
    allow_action: bool = Field(
        default=True,
        description="是否允许 Agent 执行动作，用来观察普通回答和执行动作的区别",
    )
    max_steps: int = Field(
        default=3,
        description="最大步骤数。当前模块只做概念展示，真正循环会在后续模块学习",
    )


@app.get("/health")
def health() -> dict[str, str]:
    # 最简单的健康检查接口，用于确认服务已经启动。
    return {
        "status": "ok",
        "module": "00_what_is_agent",
    }


@app.post("/chat/basic")
def chat_basic(payload: ChatRequest) -> dict[str, Any]:
    # 普通聊天：收到一句话，返回一句回答。
    # 它没有目标拆解，也不会执行动作。
    return basic_chat_reply(message=payload.message)


@app.post("/agent/run")
def agent_run(payload: AgentRunRequest) -> dict[str, Any]:
    # 最小 Agent：收到目标，先决定动作，再执行动作，最后根据观察结果回答。
    # payload.goal、payload.allow_action、payload.max_steps 都来自请求体 JSON。
    return run_minimal_agent(
        goal=payload.goal,
        allow_action=payload.allow_action,
        max_steps=payload.max_steps,
    )

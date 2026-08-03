from typing import Any

from context_builder import build_context
from provider import generate_model_answer
from schemas import ContextBuildRequest


def run_context_agent(payload: dict[str, Any]) -> dict[str, Any]:
    # agent.py 负责串起完整流程。
    # Java 类比：它更像 Service 层，不直接处理 HTTP，也不直接关心 .env。
    #
    # 输入：
    # - payload 来自 main.py 的请求体。
    #
    # 处理：
    # - 先用 ContextBuildRequest 校验输入。
    # - 再调用 build_context() 构造模型可见上下文。
    # - 最后调用 mock 或 DeepSeek 生成回答。
    #
    # 输出：
    # - answer 是模型回答。
    # - context 是本次模型真正看到的消息列表和裁剪记录。
    request = ContextBuildRequest.model_validate(payload)
    context = build_context(request)
    answer = generate_model_answer(context)

    return {
        "status": "succeeded",
        "answer": answer,
        "context": context.model_dump(),
    }

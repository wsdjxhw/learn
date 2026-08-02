from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import run_agent_with_prompt
from prompt_store import list_prompt_versions, load_prompt
from settings import get_prompt_version
from tools import list_tool_schemas


# main.py 负责 Web API 层。
# Java 类比：可以把它理解成 Controller。
# 本模块的重点不是 Controller 写法，而是 prompt 如何从代码中拆出去、如何按版本加载、如何比较行为。
app = FastAPI(title="Prompt Engineering Teaching Demo")


class PromptRunRequest(BaseModel):
    # BaseModel 类似 Java 请求 DTO。
    # FastAPI 会把用户在 /docs 中提交的 JSON 自动转换成这个对象。
    message: str = Field(
        default="客户说商品破损，订单 240 元，购买 5 天，帮我判断退款金额。",
        description="用户输入。mock model 会根据这个问题和 prompt 版本决定是否调用工具。",
    )
    prompt_version: str | None = Field(
        default=None,
        description="要使用的 prompt 版本；为空时读取 .env 里的 PROMPT_VERSION。",
    )
    order_amount: float = Field(default=240, ge=0, description="订单金额，单位元。")
    days_since_purchase: int = Field(default=5, ge=0, description="购买后经过天数。")
    item_problem: str = Field(default="破损", description="商品问题，例如：破损、不喜欢。")


class PromptCompareRequest(BaseModel):
    # compare 接口用于观察“同一个输入，不同 prompt 版本会有什么不同结果”。
    message: str = Field(
        default="客户说商品破损，订单 240 元，购买 5 天，帮我判断退款金额。",
        description="用户输入。",
    )
    versions: list[str] = Field(
        # default_factory 用来生成默认列表。
        # Python 里不建议把可变列表直接当默认值；虽然 Pydantic 会做保护，但这里按普通 Python 好习惯写。
        default_factory=lambda: ["v1_direct_answer", "v2_tool_first"],
        description="要对比的 prompt 版本列表。",
    )
    order_amount: float = Field(default=240, ge=0, description="订单金额，单位元。")
    days_since_purchase: int = Field(default=5, ge=0, description="购买后经过天数。")
    item_problem: str = Field(default="破损", description="商品问题，例如：破损、不喜欢。")


@app.get("/health")
def health() -> dict[str, Any]:
    # 用于确认服务是否启动，以及默认 prompt 版本从哪里来。
    return {
        "status": "ok",
        "module": "04_prompt_engineering",
        "default_prompt_version": get_prompt_version(),
        "available_prompt_versions": [
            item["version"] for item in list_prompt_versions()
        ],
        "tool_count": len(list_tool_schemas()),
    }


@app.get("/tools")
def tools() -> dict[str, Any]:
    # 查看工具清单。
    # prompt 只决定“是否应该调用工具”，真正允许调用哪些工具仍然由后端白名单决定。
    return {
        "tools": list_tool_schemas(),
    }


@app.get("/prompts")
def prompts() -> dict[str, Any]:
    # 查看所有 prompt 版本。
    # first_line 和 behavior 帮助学习者快速看出不同版本的目的。
    return {
        "default_prompt_version": get_prompt_version(),
        "prompts": list_prompt_versions(),
    }


@app.get("/prompts/{version}")
def prompt_detail(version: str) -> dict[str, Any]:
    # version 来自 URL 路径参数。
    # 例如 GET /prompts/v2_tool_first 时，FastAPI 会把 v2_tool_first 传给这个函数。
    try:
        return load_prompt(version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/agent/run")
def run_agent_api(payload: PromptRunRequest) -> dict[str, Any]:
    # prompt_version 优先使用请求体；请求体为空时使用 .env 的 PROMPT_VERSION。
    # 这样可以同时练习“接口参数覆盖默认配置”和“默认配置从 .env 读取”。
    prompt_version = payload.prompt_version or get_prompt_version()
    case = payload.model_dump()
    case["prompt_version"] = prompt_version
    try:
        result = run_agent_with_prompt(case=case, prompt_version=prompt_version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "request": case,
        "result": result,
    }


@app.post("/agent/compare")
def compare_prompt_versions(payload: PromptCompareRequest) -> dict[str, Any]:
    # compare 接口用同一个 case 运行多个 prompt 版本。
    # 这能直接看到 prompt 改动如何影响工具选择、工具次数和最终回答。
    case = payload.model_dump()
    results: list[dict[str, Any]] = []
    for version in payload.versions:
        try:
            result = run_agent_with_prompt(case=case, prompt_version=version)
            results.append(
                {
                    "version": version,
                    "ok": True,
                    "result": result,
                }
            )
        except FileNotFoundError as exc:
            results.append(
                {
                    "version": version,
                    "ok": False,
                    "error": str(exc),
                }
            )

    return {
        "request": case,
        "results": results,
    }

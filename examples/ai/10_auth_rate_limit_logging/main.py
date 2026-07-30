import time
from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import get_app_api_keys, get_rate_limit_per_minute
from database import (
    create_error_log,
    create_model_call_log,
    create_request_log,
    get_cost_summary,
    init_db,
    list_error_logs,
    list_model_call_logs,
    list_request_logs,
)
from provider import generate_reply, get_model_name, get_provider_name
from security import AuthContext, RateLimitContext, check_rate_limit, require_api_key

app = FastAPI(title="Auth Rate Limit Logging")


class ChatRequest(BaseModel):
    # 请求 DTO：客户端调用 /chat 时传入 message 和 system_prompt。
    # 类比 Java 里的 ChatRequest，不是 ORM Entity，也不会直接映射数据库表。
    message: str
    system_prompt: str = "You are a helpful assistant."


def validate_limit(limit: int) -> int:
    # limit 来自查询参数，用来控制日志列表最多返回多少条。
    # 限制最大值可以避免一次性返回太多日志，拖慢接口。
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be greater than 0")
    return min(limit, 100)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next: Callable) -> JSONResponse:
    # middleware 可以理解成 Java Web 里的 Filter。
    # 每个请求都会先经过这里，再进入具体接口函数。
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        api_key_hash = getattr(request.state, "api_key_hash", None)
        client_host = request.client.host if request.client else None
        create_request_log(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            api_key_hash=api_key_hash,
            client_host=client_host,
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # 统一错误响应：所有 HTTPException 都返回同一种结构。
    # 这样前端不用猜错误字段到底叫 detail、message 还是 error。
    api_key_hash = getattr(request.state, "api_key_hash", None)
    create_error_log(
        path=request.url.path,
        status_code=exc.status_code,
        error_type="HTTPException",
        message=str(exc.detail),
        api_key_hash=api_key_hash,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 兜底错误处理：避免未处理异常直接暴露堆栈给客户端。
    # 真实项目应该同时把完整异常堆栈写到服务端日志系统。
    api_key_hash = getattr(request.state, "api_key_hash", None)
    create_error_log(
        path=request.url.path,
        status_code=500,
        error_type=exc.__class__.__name__,
        message=str(exc),
        api_key_hash=api_key_hash,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "message": "Internal server error",
                "status_code": 500,
            }
        },
    )


def authenticated_context(auth: AuthContext = Depends(require_api_key)) -> AuthContext:
    # Depends(require_api_key) 可以理解成 FastAPI 自动执行鉴权逻辑。
    # 如果鉴权失败，接口函数本身不会继续执行。
    return auth


def limited_context(auth: AuthContext = Depends(require_api_key)) -> RateLimitContext:
    # 这里把鉴权和限流串起来：
    # 1. 先确认 X-API-Key 是否有效。
    # 2. 再检查这个 key 最近一分钟是否超过调用次数。
    return check_rate_limit(auth)


@app.get("/health")
def health() -> dict:
    # health 不需要 API Key，方便先确认服务是否启动。
    return {
        "status": "ok",
        "provider": get_provider_name(),
        "model": get_model_name(),
        "configured_api_key_count": len(get_app_api_keys()),
        "rate_limit_per_minute": get_rate_limit_per_minute(),
    }


@app.get("/auth/check")
def auth_check(rate: RateLimitContext = Depends(limited_context)) -> dict:
    # 这个接口专门用于测试鉴权和限流。
    return {
        "ok": True,
        "api_key_hash": rate.auth.api_key_hash,
        "rate_limit": rate.limit,
        "remaining": rate.remaining,
        "reset_after_seconds": rate.reset_after_seconds,
    }


@app.post("/chat")
def chat(
    payload: ChatRequest,
    rate: RateLimitContext = Depends(limited_context),
) -> dict:
    # /chat 是受保护接口：
    # - 没有 X-API-Key 会返回 401。
    # - key 错误会返回 403。
    # - 超过限流会返回 429。
    cleaned_message = payload.message.strip()
    if not cleaned_message:
        raise HTTPException(status_code=400, detail="message must not be empty")

    if rate.auth.raw_api_key.split("-")[0] != "dev":
        raise HTTPException(status_code=403, detail="Only dev API keys can be used for this endpoint")
    
    try:
        result = generate_reply(
            user_message=cleaned_message,
            system_prompt=payload.system_prompt,
        )
        create_model_call_log(
            provider=result["provider"],
            model=result["model"],
            success=True,
            prompt_chars=result["prompt_chars"],
            reply_chars=result["reply_chars"],
            estimated_input_tokens=result["estimated_input_tokens"],
            estimated_output_tokens=result["estimated_output_tokens"],
            estimated_cost_usd=result["estimated_cost_usd"],
        )
    except Exception as error:
        # 模型调用失败也要记录一次 model_call_logs，方便后续排查。
        create_model_call_log(
            provider=get_provider_name(),
            model=get_model_name(),
            success=False,
            prompt_chars=len(payload.system_prompt) + len(cleaned_message),
            reply_chars=0,
            estimated_input_tokens=0,
            estimated_output_tokens=0,
            estimated_cost_usd=0.0,
            error_message=str(error),
        )
        raise HTTPException(status_code=502, detail="Model call failed") from error

    return {
        "message": cleaned_message,
        "reply": result["reply"],
        "provider": result["provider"],
        "model": result["model"],
        "usage": {
            "estimated_input_tokens": result["estimated_input_tokens"],
            "estimated_output_tokens": result["estimated_output_tokens"],
            "estimated_cost_usd": result["estimated_cost_usd"],
        },
        "rate_limit": {
            "limit": rate.limit,
            "remaining": rate.remaining,
            "reset_after_seconds": rate.reset_after_seconds,
        },
    }


@app.get("/logs/requests")
def get_request_logs(
    limit: int = Query(20),
    auth: AuthContext = Depends(authenticated_context),
) -> dict:
    # 查询请求日志也要鉴权，但这里不做限流，避免排查问题时日志接口被限流挡住。
    checked_limit = validate_limit(limit)
    return {"api_key_hash": auth.api_key_hash, "items": list_request_logs(checked_limit)}


@app.get("/logs/errors")
def get_error_logs(
    limit: int = Query(20),
    auth: AuthContext = Depends(authenticated_context),
) -> dict:
    checked_limit = validate_limit(limit)
    return {"api_key_hash": auth.api_key_hash, "items": list_error_logs(checked_limit)}


@app.get("/logs/model-calls")
def get_model_logs(
    limit: int = Query(20),
    auth: AuthContext = Depends(authenticated_context),
) -> dict:
    checked_limit = validate_limit(limit)
    return {"api_key_hash": auth.api_key_hash, "items": list_model_call_logs(checked_limit)}


@app.get("/stats/costs")
def get_costs(auth: AuthContext = Depends(authenticated_context)) -> dict:
    # 成本统计用来观察模型调用数量和估算成本。
    # 这里返回的是教学估算，不代表真实账单。
    return {"api_key_hash": auth.api_key_hash, "summary": get_cost_summary()}

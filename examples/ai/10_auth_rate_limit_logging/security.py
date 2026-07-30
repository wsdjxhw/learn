import hashlib
import time
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from config import get_app_api_keys, get_rate_limit_per_minute

WINDOW_SECONDS = 60
REQUEST_BUCKETS: dict[str, list[float]] = {}


@dataclass
class AuthContext:
    # dataclass 可以理解成一个轻量 DTO。
    # 这里把认证结果统一装起来，后续日志和接口返回都可以复用。
    api_key_hash: str
    raw_api_key: str


@dataclass
class RateLimitContext:
    # 限流依赖返回这个对象，方便接口告诉调用方还剩多少请求额度。
    auth: AuthContext
    limit: int
    remaining: int
    reset_after_seconds: int


def hash_api_key(api_key: str) -> str:
    # 日志里不要保存原始 API Key。
    # hash 后只保留前 12 位，足够用于区分调用方，又不会暴露完整密钥。
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthContext:
    # x_api_key 来自请求头 X-API-Key。
    # Header(...) 告诉 FastAPI：这个参数不是路径参数、查询参数或请求体，而是 HTTP Header。
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key not in get_app_api_keys():
        raise HTTPException(status_code=403, detail="Invalid API key")

    auth = AuthContext(api_key_hash=hash_api_key(x_api_key), raw_api_key=x_api_key)
    # request.state 是 FastAPI/Starlette 提供的“本次请求临时存储”。
    # middleware 里可以读取它，把 api_key_hash 写入请求日志。
    request.state.api_key_hash = auth.api_key_hash
    return auth


def check_rate_limit(auth: AuthContext) -> RateLimitContext:
    # 这是教学版内存限流。
    # 真实项目通常会用 Redis，因为多进程、多服务器时，内存字典不能共享。
    now = time.time()
    limit = get_rate_limit_per_minute()
    bucket = REQUEST_BUCKETS.setdefault(auth.api_key_hash, [])

    # 只保留最近 60 秒内的请求时间。
    recent_requests = [timestamp for timestamp in bucket if now - timestamp < WINDOW_SECONDS]
    REQUEST_BUCKETS[auth.api_key_hash] = recent_requests

    if len(recent_requests) >= limit:
        oldest = min(recent_requests)
        reset_after_seconds = max(1, int(WINDOW_SECONDS - (now - oldest)))
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_after_seconds} seconds.",
        )

    recent_requests.append(now)
    remaining = limit - len(recent_requests)
    reset_after_seconds = WINDOW_SECONDS
    return RateLimitContext(
        auth=auth,
        limit=limit,
        remaining=remaining,
        reset_after_seconds=reset_after_seconds,
    )

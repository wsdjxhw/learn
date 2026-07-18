from fastapi import FastAPI
from pydantic import BaseModel

# FastAPI 实例负责注册路由和启动整个 Web 应用。
app = FastAPI(title="Learning FastAPI")


class EchoRequest(BaseModel):
    # Pydantic 模型会自动校验请求体字段。
    message: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/echo")
def echo(payload: EchoRequest) -> dict:
    # 这个接口演示“接收 JSON -> 处理 -> 返回 JSON”的最小闭环。
    return {
        "original": payload.message,
        "upper": payload.message.upper(),
        "length": len(payload.message),
        "lower": payload.message.lower()
    }

@app.get("/hello")
def hello() -> dict:
    return{"pg": "Hello, FastAPI!"}

import os
from pathlib import Path

from dotenv import load_dotenv

PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_APP_API_KEYS = "dev-key-123"
DEFAULT_RATE_LIMIT_PER_MINUTE = 5

# 所有配置统一从本模块同目录的 .env 读取。
# 这样 main.py、security.py、provider.py 不需要各自猜配置在哪里。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_deepseek_api_key() -> str | None:
    # DeepSeek key 是“调用外部模型服务”的密钥，不等于用户访问本 API 的 key。
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        return None
    return api_key


def get_deepseek_model() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def get_app_api_keys() -> set[str]:
    # APP_API_KEYS 是访问本 FastAPI 服务的 API Key。
    # 支持逗号分隔，方便本地模拟多个调用方。
    raw_value = os.getenv("APP_API_KEYS", DEFAULT_APP_API_KEYS)
    keys = {item.strip() for item in raw_value.split(",") if item.strip()}
    if not keys:
        return {DEFAULT_APP_API_KEYS}
    return keys


def get_rate_limit_per_minute() -> int:
    # 限流值来自 .env。配置读取后转成 int，因为环境变量本质都是字符串。
    raw_value = os.getenv("RATE_LIMIT_PER_MINUTE", str(DEFAULT_RATE_LIMIT_PER_MINUTE))
    try:
        limit = int(raw_value)
    except ValueError:
        return DEFAULT_RATE_LIMIT_PER_MINUTE

    if limit <= 0:
        return DEFAULT_RATE_LIMIT_PER_MINUTE
    return limit

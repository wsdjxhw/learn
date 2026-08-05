import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


# load_dotenv() 会读取当前目录下的 .env。
# 如果没有 .env，本模块仍然能用 mock 模式直接运行。
load_dotenv()


@dataclass
class Settings:
    # dataclass 是 Python 标准库里的轻量数据类。
    # Java 类比：可以理解成只承载配置字段的 POJO。
    model_mode: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    database_url: str


@lru_cache
def get_settings() -> Settings:
    # lru_cache 会让配置只构造一次。
    # 真实项目通常也会在应用启动时统一加载配置，而不是每个请求都读环境变量。
    return Settings(
        model_mode=os.getenv("MODEL_MODE", "mock").lower(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./agent_memory_governance.db"),
    )

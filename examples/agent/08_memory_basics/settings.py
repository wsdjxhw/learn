import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


# load_dotenv() 会读取当前目录的 .env 文件。
# 没有 .env 也不会报错，因为本模块默认 MODEL_MODE=mock，可以无 key 跑通。
load_dotenv()


@dataclass
class Settings:
    # dataclass 是 Python 标准库里的轻量数据类。
    # Java 类比：可以理解成只保存配置字段的 POJO。
    model_mode: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    database_url: str


@lru_cache
def get_settings() -> Settings:
    # lru_cache 会缓存函数返回值。
    # 对配置来说，这表示服务启动后只读取一次环境变量，避免每个请求反复读配置。
    return Settings(
        model_mode=os.getenv("MODEL_MODE", "mock").lower(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./agent_memory.db"),
    )

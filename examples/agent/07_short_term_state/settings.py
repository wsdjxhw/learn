import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


# load_dotenv() 会读取当前目录下的 .env 文件。
# 如果没有 .env，也不会报错，因为教学模块默认可以用 mock 模式直接跑通。
load_dotenv()


@dataclass
class Settings:
    # dataclass 是 Python 标准库提供的轻量配置对象。
    # Java 类比：可以理解成一个只装配置字段的 POJO。
    model_mode: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    database_url: str


@lru_cache
def get_settings() -> Settings:
    # lru_cache 会让 Settings 只创建一次。
    # 这比每个请求都重新读环境变量更稳定，也更接近真实项目的配置加载方式。
    return Settings(
        model_mode=os.getenv("MODEL_MODE", "mock").lower(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./agent_state.db"),
    )

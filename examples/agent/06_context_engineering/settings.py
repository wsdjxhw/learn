import os
from dataclasses import dataclass

from dotenv import load_dotenv


# load_dotenv() 会读取当前目录下的 .env 文件。
# Java 类比：可以理解成 Spring Boot 启动时读取 application.properties。
# 本模块默认 MODEL_MODE=mock，所以没有真实模型密钥也能完整跑通上下文构造流程。
load_dotenv()


@dataclass
class Settings:
    # dataclass 用来表达“配置对象有哪些字段”。
    # 比直接到处使用 os.getenv() 更清楚，也更方便以后统一校验配置。
    model_mode: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str


def get_settings() -> Settings:
    # os.getenv("NAME", "default") 表示：
    # - 如果环境变量 NAME 存在，就读取真实值。
    # - 如果不存在，就使用 default。
    #
    # 这里每次调用都重新读取，是为了让初学者能清楚看到配置从 .env 来。
    return Settings(
        model_mode=os.getenv("MODEL_MODE", "mock"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    )

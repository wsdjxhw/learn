import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


# load_dotenv() 会读取当前目录下的 .env 文件。
# 如果没有 .env，本模块默认使用 mock 模式和教学用 API Key，保证没有真实密钥也能跑通。
load_dotenv()


@dataclass
class Settings:
    # Settings 是配置对象。
    # Java 类比：可以理解成只保存配置字段的 POJO，不负责业务逻辑。
    model_mode: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    database_url: str
    learner_api_key: str
    operator_api_key: str
    admin_api_key: str


@lru_cache
def get_settings() -> Settings:
    # lru_cache 让配置只读取一次。
    # 初学者常见误区：每个接口里反复 os.getenv() 也能跑，但真实项目会让配置入口分散。
    return Settings(
        model_mode=os.getenv("MODEL_MODE", "mock").lower(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./agent_rag_tool_agent.db"),
        learner_api_key=os.getenv("LEARNER_API_KEY", "learner-key"),
        operator_api_key=os.getenv("OPERATOR_API_KEY", "operator-key"),
        admin_api_key=os.getenv("ADMIN_API_KEY", "admin-key"),
    )

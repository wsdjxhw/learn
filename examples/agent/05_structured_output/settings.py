import os
from dataclasses import dataclass

from dotenv import load_dotenv


# load_dotenv() 会读取当前目录下的 .env 文件。
# Java 类比：可以理解成应用启动时读取 application.properties。
# 本模块默认 MODEL_MODE=mock，所以没有 DEEPSEEK_API_KEY 也能跑通。
load_dotenv()


@dataclass
class Settings:
    # dataclass 用来保存配置对象。
    # 它比普通 dict 更清楚：这里有哪些配置、每个配置叫什么。
    model_mode: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str


def get_settings() -> Settings:
    # os.getenv("NAME", "default") 表示：
    # - 如果环境变量 NAME 存在，就读取它。
    # - 如果不存在，就使用第二个参数里的默认值。
    #
    # 这里不在模块加载时直接创建全局 settings，是为了让学习者修改 .env 后重启服务时更容易理解配置来源。
    return Settings(
        model_mode=os.getenv("MODEL_MODE", "mock"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    )

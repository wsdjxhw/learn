import os

from dotenv import load_dotenv


# load_dotenv() 会读取当前目录下的 .env 文件。
# Java 类比：它有点像读取 application.properties，把配置放进程序运行环境。
# 本模块用 .env 控制默认 prompt 版本，学习“prompt 也是可配置资产”。
load_dotenv()


def get_prompt_version() -> str:
    # os.getenv("PROMPT_VERSION", "v2_tool_first") 的意思是：
    # 先从环境变量读取 PROMPT_VERSION；如果没有配置，就使用 v2_tool_first。
    # 这样没有 .env 文件也能运行，符合教学示例“先能跑起来”的原则。
    return os.getenv("PROMPT_VERSION", "v2_tool_first")


def get_prompt_dir() -> str:
    # PROMPT_DIR 默认指向本模块下的 prompts 目录。
    # 后续如果要做更复杂的 prompt 管理，可以把它换成数据库、对象存储或配置中心。
    return os.getenv("PROMPT_DIR", "prompts")

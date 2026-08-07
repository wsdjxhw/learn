"""
settings.py —— 项目配置模块

这个文件集中管理整个模块的配置项：数据库地址、API Key、模型参数、Agent 步数上限等。
为什么需要它？如果没有它，这些配置会散落在各个文件里，想改一个数据库地址就要翻遍所有文件。

初学者容易卡住的地方：
- 这里用的是 pydantic-settings 的 BaseSettings，它在导入时自动读取根目录的 .env 文件。
- 字段名和 .env 里的变量名一一对应且不区分大小写：
    代码字段   database_url  <->  .env 变量  DATABASE_URL
- mock_mode 是本项目的核心开关：等于 True 时完全不调用外部模型，没有 API Key 也能跑。
- 真实项目里配置会来自环境变量 / 配置文件 / 配置中心，绝不会硬编码在代码里。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有配置项的集中定义。

    说明：BaseSettings 的每个字段都带默认值，所以就算没有 .env 文件也能运行
    （默认就是 mock 模式 + SQLite）。
    """

    app_name: str = "数据库工具智能体"

    # 数据库连接串。默认用 SQLite 本地文件，零依赖可跑。
    # 真实项目会换成 PostgreSQL，例如：
    # postgresql+psycopg://user:password@localhost:5432/agent_db
    database_url: str = "sqlite:///./agent_database.db"

    # true=用 mock 模型（无 key 可跑）；false=调用真实 DeepSeek
    mock_mode: bool = True

    # DeepSeek 配置（MOCK_MODE=false 时才用到）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 三个角色的 API Key，请求时通过请求头 X-API-Key 携带
    viewer_api_key: str = "sk-viewer-0000000001"
    operator_api_key: str = "sk-operator-0000000001"
    admin_api_key: str = "sk-admin-0000000001"

    # Agent 循环最大步数：防止模型陷入"无限调工具"的死循环
    max_agent_steps: int = 3

    # 告诉 BaseSettings 去读哪个文件，以及编码格式
    model_config = SettingsConfigDict(
        env_file=".env",          # 读取当前目录下的 .env 文件
        env_file_encoding="utf-8",# 文件用 utf-8 编码（防止中文注释乱码）
        extra="ignore",           # .env 里多出来的变量忽略掉，不报错
    )


# 模块级单例：整个项目共享同一个配置对象
# 这样任何文件 `from settings import settings` 拿到的都是同一份配置
settings = Settings()

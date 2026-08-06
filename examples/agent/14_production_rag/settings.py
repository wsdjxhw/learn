"""
settings.py - 配置读取层

职责：从 .env 文件（或环境变量）读取本模块需要的所有配置。
    其它文件不要自己读环境变量，统一从这里拿，避免配置来源散落各处。

真实项目里，这个文件通常还会：
- 区分 dev / staging / prod 多套环境配置；
- 校验必填项缺失时直接启动失败（fail fast），而不是运行到一半才报错；
- 敏感信息（密钥）不打印到日志。

教学版简化：只做最基础的读取 + 默认值兜底，保证不配置也能跑。
"""
import os

from dotenv import load_dotenv

# 加载 .env 文件里的配置到进程环境变量。
# 这样 os.getenv() 就能读到 .env 里的值；没有 .env 文件时也不会报错。
load_dotenv()


class Settings:
    """一个简单的配置类，用属性把所有配置集中起来。

    类比 Java：相当于一个 @ConfigurationProperties 的配置类，
    或者 Spring 的 application.yml 在代码里的对应物。
    """

    def __init__(self) -> None:
        # 模型运行模式：mock（默认，不调真实模型）或 deepseek（真实调用）
        self.model_mode = os.getenv("MODEL_MODE", "mock")

        # DeepSeek 配置，通过 openai 包的 OpenAI 兼容协议调用
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        # 数据库连接串。默认 SQLite 文件，第一次启动自动创建。
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./agent_production_rag.db")

        # 教学 API Key -> 用户身份的映射。
        # 注意：这不是真实鉴权，只是用来说明“不同用户能看到不同的文档”。
        self.learner_api_key = os.getenv("LEARNER_API_KEY", "learner-key")
        self.operator_api_key = os.getenv("OPERATOR_API_KEY", "operator-key")
        self.admin_api_key = os.getenv("ADMIN_API_KEY", "admin-key")

        # 检索相关默认参数（可被请求体覆盖）
        self.default_top_k = int(os.getenv("RAG_TOP_K", "20"))   # 召回候选数（粗排后）
        self.default_top_n = int(os.getenv("RAG_TOP_N", "3"))    # 最终进入回答的片段数（精排后）
        self.chunk_max_chars = int(os.getenv("CHUNK_MAX_CHARS", "300"))  # 切分时每段目标字数
        # 相关性阈值：精排分低于该值的片段不进入回答，视为“资料不足”。
        # 这是真实 RAG 防误导的关键：检索到内容 ≠ 检索到正确答案。
        self.rag_min_score = float(os.getenv("RAG_MIN_SCORE", "0.25"))


# 模块级单例：整个进程共享同一个配置对象，避免每个文件都 new 一份。
settings = Settings()

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    # BaseModel 是 Pydantic 的数据模型。
    # Java 类比：这里更像请求 DTO，不是数据库 Entity。
    # FastAPI 会用它校验请求体里的 history 每一项是否有 role 和 content。
    role: Literal["user", "assistant"] = Field(description="历史消息角色，只允许 user 或 assistant。")
    content: str = Field(min_length=1, description="历史消息内容，不能为空。")


class RagSource(BaseModel):
    # RagSource 表示检索系统返回的一条资料片段。
    # 注意：它不是最终回答，只是准备塞进模型上下文的候选资料。
    source_id: str = Field(description="资料 ID，方便最终回答引用来源。")
    title: str = Field(min_length=1, description="资料标题。")
    content: str = Field(min_length=1, description="资料正文片段。")
    relevance_score: float = Field(ge=0, le=1, description="相关性分数，教学版用 0 到 1 表示。")
    reason: str = Field(
        default="",
        description="练习二：检索系统为什么认为这条资料相关。放进上下文，让模型不仅看到资料，还看到检索理由。",
    )


class ToolObservation(BaseModel):
    # observation 是工具执行后的观察结果。
    # Agent 循环里常见链路是：模型决定调用工具 -> 后端执行工具 -> 把 observation 再给模型看。
    tool_name: str = Field(min_length=1, description="工具名称。")
    success: bool = Field(description="工具是否执行成功。")
    content: str = Field(min_length=1, description="工具返回的结果或错误说明。")
    operation_kind: Literal["read", "write", "other"] = Field(
        default="read",
        description="练习三：工具操作类型。write 表示会改变业务状态的写操作，风险和价值更高。",
    )


class ContextBuildRequest(BaseModel):
    # 这个请求 DTO 覆盖本模块的主要输入：
    # - 当前用户问题。
    # - 历史消息。
    # - RAG 检索结果。
    # - 工具 observation。
    #
    # 初学者要特别注意：这些输入不会原样全部塞给模型，而是会经过 context_builder.py 筛选和裁剪。
    message: str = Field(min_length=1, description="当前用户问题。")
    context_scenario: Literal["clean", "long_history", "noisy_rag", "tool_result", "tool_error"] = Field(
        default="clean",
        description="教学场景。不传 history、rag_sources、tool_observations 时，会按场景生成示例数据。",
    )
    max_context_tokens: int = Field(
        default=700,
        ge=220,
        le=2000,
        description="教学版 token 预算。这里用近似算法，不等同于真实 tokenizer。",
    )
    max_history_messages: int = Field(
        default=6,
        ge=0,
        le=20,
        description="最多保留多少条最近历史消息。",
    )
    rag_min_relevance: float = Field(
        default=0.55,
        ge=0,
        le=1,
        description="RAG 资料进入上下文的最低相关性分数。",
    )
    include_low_relevance_sources: bool = Field(
        default=False,
        description="是否故意把低相关资料也放进上下文，用来观察干扰效果。",
    )
    history: list[ChatMessage] | None = Field(
        default=None,
        description="可选历史消息。不传时使用 sample_data.py 里的教学数据。",
    )
    rag_sources: list[RagSource] | None = Field(
        default=None,
        description="可选 RAG 资料。不传时使用 sample_data.py 里的教学数据。",
    )
    tool_observations: list[ToolObservation] | None = Field(
        default=None,
        description="可选工具 observation。不传时使用 sample_data.py 里的教学数据。",
    )


class ContextMessage(BaseModel):
    # 这是最终会交给模型的一条消息。
    # role 是模型协议需要的角色；source_type 和 keep_reason 是教学字段，方便你看懂为什么保留它。
    role: Literal["system", "user", "assistant"]
    content: str
    source_type: Literal["system_prompt", "history", "rag", "tool_observation", "current_user"]
    approx_tokens: int
    keep_reason: str


class OmittedContextItem(BaseModel):
    # 被丢弃的上下文也要记录原因。
    # 真实工程排查 Agent 问题时，经常要问：为什么某条历史或某个 source 没有进入 prompt？
    source_type: str
    summary: str
    approx_tokens: int
    omit_reason: str


class ContextStats(BaseModel):
    # 练习四：给 /context/preview 增加前端友好的统计字段。
    # 真实项目里这些数字会用于调试工作台、token 成本预估和上下文质量监控。
    history_count_kept: int = Field(description="保留了多少条历史消息。")
    rag_count_kept: int = Field(description="保留了多少条 RAG 资料。")
    tool_observation_count_kept: int = Field(description="保留了多少条工具 observation。")
    omitted_count: int = Field(description="丢弃了多少条上下文。")


class ContextBuildResult(BaseModel):
    messages: list[ContextMessage]
    omitted_items: list[OmittedContextItem]
    total_approx_tokens: int
    max_context_tokens: int
    policy: dict[str, str | int | float | bool]
    context_stats: ContextStats = Field(
        description="练习四：前端友好的上下文统计，方便工作台和可观测性展示。"
    )

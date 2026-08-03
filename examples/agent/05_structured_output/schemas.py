from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


MockScenario = Literal[
    "valid_json",
    "json_with_extra_text",
    "missing_field",
    "wrong_type",
    "invalid_enum",
    "broken_json",
]


class StructuredRunRequest(BaseModel):
    # BaseModel 类似 Java 里的请求 DTO。
    # FastAPI 会把 /docs 里提交的 JSON 请求体转换成这个对象，并自动检查字段类型。
    message: str = Field(
        default="客户说商品破损，订单 240 元，购买 5 天，帮我判断退款金额。",
        description="用户输入。模型需要把这段自然语言变成结构化决策。",
    )
    order_amount: float = Field(default=240, ge=0, description="订单金额，单位元。")
    days_since_purchase: int = Field(default=5, ge=0, description="购买后经过天数。")
    item_problem: str = Field(default="破损", description="商品问题，例如：破损、不喜欢、物流慢。")
    allow_retry: bool = Field(
        default=True,
        description="解析或校验失败后，是否允许后端要求模型按错误信息重试一次。",
    )
    mock_scenario: MockScenario = Field(
        default="valid_json",
        description="mock 模型的输出场景，用来稳定演示解析失败和校验失败。",
    )


class StructuredCompareRequest(BaseModel):
    # compare 接口不是生产必需接口，它是教学用的。
    # 同一个业务输入配不同 mock_scenario，可以观察后端如何处理各种坏输出。
    message: str = Field(
        default="客户说商品破损，订单 240 元，购买 5 天，帮我判断退款金额。",
        description="用户输入。",
    )
    order_amount: float = Field(default=240, ge=0, description="订单金额，单位元。")
    days_since_purchase: int = Field(default=5, ge=0, description="购买后经过天数。")
    item_problem: str = Field(default="破损", description="商品问题。")
    allow_retry: bool = Field(default=True, description="是否允许重试一次。")
    scenarios: list[MockScenario] = Field(
        default_factory=lambda: [
            "valid_json",
            "missing_field",
            "wrong_type",
            "invalid_enum",
            "broken_json",
        ],
        description="要批量对比的 mock 输出场景。",
    )


class ToolAction(BaseModel):
    # 这个类描述“后端下一步应该做什么”。
    # 注意：模型只是在 JSON 里建议 action，真实项目仍然要由后端做工具白名单、权限和参数校验。
    tool_name: Literal["search_refund_policy", "calculate_refund", "manual_review"] = Field(
        description="允许的工具名。Literal 类似 Java enum，只允许固定几个值。",
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="工具参数。这里先用 dict 承载，后续工具工程模块会继续细化每个工具的参数 schema。",
    )
    reason: str = Field(description="为什么需要这个动作。")


class RefundDecision(BaseModel):
    # 这是本模块最重要的“输出契约”。
    # Java 类比：可以理解成模型必须返回的 Response DTO。
    #
    # ConfigDict(extra="forbid") 表示不允许模型偷偷多返回未知字段。
    # 真实项目里这很重要：字段悄悄变多，往往意味着 prompt 或模型行为已经偏离后端契约。
    model_config = ConfigDict(extra="forbid")

    decision_type: Literal["tool_call", "final_answer", "manual_review"] = Field(
        description="后端如何处理这次结果：调用工具、直接回答、转人工。",
    )
    category: Literal["refund", "exchange", "shipping", "other"] = Field(
        description="问题分类。枚举值固定，方便后端统计和分流。",
    )
    priority: Literal["low", "medium", "high"] = Field(
        description="处理优先级。非法值会被 Pydantic 拒绝。",
    )
    summary: str = Field(min_length=1, description="给内部客服看的简短摘要。")
    missing_fields: list[str] = Field(
        default_factory=list,
        description="还缺哪些信息。空列表表示信息足够。",
    )
    risk_flags: list[str] = Field(
        default_factory=list,
        description="风险标记，例如 high_amount、over_policy_days。",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="模型对结构化判断的置信度，必须在 0 到 1 之间。",
    )
    action: ToolAction | None = Field(
        default=None,
        description="下一步动作。decision_type 是 tool_call 或 manual_review 时通常需要它。",
    )
    user_visible_answer: str = Field(
        min_length=1,
        description="可以展示给用户看的回答。不能只给内部字段，不给用户解释。",
    )

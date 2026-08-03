from schemas import ChatMessage, RagSource, ToolObservation


def demo_history(scenario: str) -> list[ChatMessage]:
    # 教学数据的作用不是模拟完整数据库，而是让你不用先写聊天历史系统也能观察上下文裁剪。
    # 后续短期状态和记忆模块会再把这些数据放进数据库。
    base_history = [
        ChatMessage(role="user", content="我上次问过退款规则，你说要看购买天数和商品问题。"),
        ChatMessage(role="assistant", content="是的，售后判断通常需要购买天数、订单金额、商品问题和证据材料。"),
        ChatMessage(role="user", content="订单金额是 240 元。"),
        ChatMessage(role="assistant", content="已记录订单金额 240 元，还需要知道购买后天数和具体问题。"),
    ]

    if scenario != "long_history":
        return base_history

    old_messages = [
        ChatMessage(role="user", content="我想了解会员积分规则。"),
        ChatMessage(role="assistant", content="会员积分通常和订单金额、活动倍率有关。"),
        ChatMessage(role="user", content="你能帮我写一段店铺欢迎语吗？"),
        ChatMessage(role="assistant", content="可以，欢迎语应该简短、礼貌，并引导用户说明问题。"),
        ChatMessage(role="user", content="去年双十一有什么活动？"),
        ChatMessage(role="assistant", content="历史活动需要以当时公告为准。"),
        ChatMessage(role="user", content="我还问过一次物流延迟怎么补偿。"),
        ChatMessage(role="assistant", content="物流延迟通常先查物流状态，再看平台补偿政策。"),
    ]
    return old_messages + base_history


def demo_rag_sources(scenario: str) -> list[RagSource]:
    useful_sources = [
        RagSource(
            source_id="refund-policy-001",
            title="售后退款规则",
            content="商品签收 7 天内，如果存在破损、质量问题或错发漏发，可以优先走全额退款或补发流程。",
            relevance_score=0.92,
            reason="问题包含破损关键词，命中退款规则，且商品在 7 天售后窗口内。",
        ),
        RagSource(
            source_id="refund-policy-002",
            title="超过售后窗口的处理",
            content="超过 7 天的订单不能自动退款，需要客服收集证据后转人工审核。",
            relevance_score=0.78,
            reason="问题涉及退款资格，需要同时参考窗口外处理规则。",
        ),
    ]

    if scenario != "noisy_rag":
        return useful_sources

    # 这两条资料故意相关性较低。
    # 如果它们被塞进上下文，模型可能把退款问题误判成会员或营销问题。
    noisy_sources = [
        RagSource(
            source_id="member-009",
            title="黑金会员升级规则",
            content="用户连续三个月消费满 999 元可升级黑金会员，黑金会员优先享受专属客服和生日优惠券。",
            relevance_score=0.21,
            reason="仅和会员权益相关，与退款判断无直接关系。",
        ),
        RagSource(
            source_id="campaign-2026",
            title="七夕营销活动",
            content="七夕活动期间，部分美妆商品支持满 300 减 40，但活动优惠不可兑换现金。",
            relevance_score=0.18,
            reason="仅和营销活动相关，不涉及售后退款规则。",
        ),
    ]
    return noisy_sources + useful_sources


def demo_tool_observations(scenario: str) -> list[ToolObservation]:
    if scenario == "tool_result":
        return [
            ToolObservation(
                tool_name="calculate_refund",
                success=True,
                content='{"refund_amount": 240, "currency": "CNY", "reason": "7天内破损，符合全额退款条件"}',
                operation_kind="write",
            ),
            ToolObservation(
                tool_name="search_shipment",
                success=True,
                content="物流信息查询成功：已签收。",
                operation_kind="read",
            ),
        ]

    if scenario == "tool_error":
        return [
            ToolObservation(
                tool_name="calculate_refund",
                success=False,
                content="工具执行失败：缺少签收时间，无法判断是否仍在 7 天售后窗口内。",
                operation_kind="write",
            )
        ]

    return []


def list_demo_cases() -> list[dict[str, str]]:
    return [
        {"name": "clean", "description": "少量历史 + 高相关 RAG，适合先跑通。"},
        {"name": "long_history", "description": "历史消息很多，观察只保留最近且有价值的部分。"},
        {"name": "noisy_rag", "description": "混入低相关资料，观察过滤策略如何减少干扰。"},
        {"name": "tool_result", "description": "工具成功后，把 observation 注入上下文。"},
        {"name": "tool_error", "description": "工具失败后，把失败原因注入上下文，让模型解释下一步。"},
    ]

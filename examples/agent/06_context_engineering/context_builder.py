from math import ceil

from sample_data import demo_history, demo_rag_sources, demo_tool_observations
from schemas import (
    ContextBuildRequest,
    ContextBuildResult,
    ContextMessage,
    ContextStats,
    OmittedContextItem,
)


SYSTEM_PROMPT = (
    "你是一个电商售后 Agent。"
    "回答必须优先依据工具 observation，其次依据 RAG 资料，再参考最近历史消息。"
    "如果上下文资料不足，要明确说明缺少什么信息，不要编造。"
)


def estimate_tokens(text: str) -> int:
    # 真实项目通常会用模型对应的 tokenizer 统计 token。
    # 本模块为了教学先用近似值：中文、英文、符号都按字符长度粗略折算。
    # 重点不是算得绝对准确，而是让初学者理解“上下文有预算，不能无限塞”。
    return max(1, ceil(len(text) / 2))


def _short(text: str, max_chars: int = 42) -> str:
    # 这个函数只用于 omitted_items 里的摘要，避免响应里塞太长文本。
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _fit_content(prefix: str, content: str, remaining_tokens: int) -> str | None:
    # prefix 是我们给上下文加的教学标签，例如 [RAG资料]。
    # 如果剩余预算连标签都放不下，就返回 None，表示这条上下文必须丢弃。
    prefix_tokens = estimate_tokens(prefix)
    if remaining_tokens <= prefix_tokens + 8:
        return None

    # 近似 token 与字符的换算是本模块的教学简化。
    # 为了让裁剪后的内容还可读，这里至少保留一小段正文。
    max_content_chars = max(24, (remaining_tokens - prefix_tokens) * 2)
    if len(content) <= max_content_chars:
        return prefix + content
    return prefix + content[:max_content_chars] + "..."


def _append_if_budget(
    messages: list[ContextMessage],
    omitted_items: list[OmittedContextItem],
    *,
    role: str,
    content: str,
    source_type: str,
    keep_reason: str,
    max_context_tokens: int,
    omit_summary: str,
) -> bool:
    # 这个函数集中处理“预算是否够”的判断，避免每类上下文都重复写一遍。
    # messages 是已经决定保留的上下文；omitted_items 是被丢弃的上下文审计记录。
    used_tokens = sum(item.approx_tokens for item in messages)
    remaining_tokens = max_context_tokens - used_tokens
    approx_tokens = estimate_tokens(content)

    if approx_tokens <= remaining_tokens:
        messages.append(
            ContextMessage(
                role=role,  # type: ignore[arg-type]
                content=content,
                source_type=source_type,  # type: ignore[arg-type]
                approx_tokens=approx_tokens,
                keep_reason=keep_reason,
            )
        )
        return True

    fitted_content = _fit_content("", content, remaining_tokens)
    if fitted_content:
        messages.append(
            ContextMessage(
                role=role,  # type: ignore[arg-type]
                content=fitted_content,
                source_type=source_type,  # type: ignore[arg-type]
                approx_tokens=estimate_tokens(fitted_content),
                keep_reason=keep_reason + "；内容因预算不足被截断。",
            )
        )
        return True

    omitted_items.append(
        OmittedContextItem(
            source_type=source_type,
            summary=omit_summary,
            approx_tokens=approx_tokens,
            omit_reason="超过 max_context_tokens 预算。",
        )
    )
    return False


def build_context(request: ContextBuildRequest) -> ContextBuildResult:
    # build_context() 是本模块最核心的函数。
    #
    # 输入：
    # - request.message：当前用户问题。
    # - request.history：历史消息。
    # - request.rag_sources：RAG 检索候选资料。
    # - request.tool_observations：工具执行结果。
    #
    # 处理：
    # - 先保证 system prompt 和当前问题一定进入上下文。
    # - 再按优先级选择工具 observation、RAG、最近历史。
    # - 超预算的内容会被丢弃或截断，并记录原因。
    #
    # 输出：
    # - messages：真正准备发给模型的消息。
    # - omitted_items：被丢弃的上下文和原因。
    # - policy：本次构造采用的策略参数。
    history = request.history if request.history is not None else demo_history(request.context_scenario)
    rag_sources = request.rag_sources if request.rag_sources is not None else demo_rag_sources(request.context_scenario)
    observations = (
        request.tool_observations
        if request.tool_observations is not None
        else demo_tool_observations(request.context_scenario)
    )

    omitted_items: list[OmittedContextItem] = []
    selected_messages: list[ContextMessage] = [
        ContextMessage(
            role="system",
            content=SYSTEM_PROMPT,
            source_type="system_prompt",
            approx_tokens=estimate_tokens(SYSTEM_PROMPT),
            keep_reason="系统规则优先级最高，必须保留。",
        )
    ]

    # 当前用户问题必须保留，因为它是本次模型调用的目标。
    current_user_content = f"[当前用户问题]\n{request.message}"
    current_user_message = ContextMessage(
        role="user",
        content=current_user_content,
        source_type="current_user",
        approx_tokens=estimate_tokens(current_user_content),
        keep_reason="当前用户问题是本次请求目标，必须保留。",
    )

    # ---- 工具 observation 选择（练习三）----
    # 优先级：成功的写操作 > 失败 observation（保留错误原因）> 普通查询（read）。
    # 先按优先级排序，再按预算逐条放入。
    def _observation_priority(obs) -> tuple[int, int]:
        # 返回的元组越大越优先。练习三的要求：
        # 1. 成功写操作最高。
        # 2. 失败 observation 保留错误原因（排在成功写操作之后）。
        # 3. 普通查询最低，预算不足时先被丢弃。
        if obs.success and obs.operation_kind == "write":
            return (3, 0)
        if obs.success and obs.operation_kind == "other":
            return (2, 1)
        if not obs.success:
            return (2, 0)
        return (1, 0)  # 普通读查询

    sorted_observations = sorted(observations, key=_observation_priority, reverse=True)
    for observation in sorted_observations:
        status = "成功" if observation.success else "失败"
        content = (
            f"[工具观察]\n工具：{observation.tool_name}\n"
            f"状态：{status}\n操作类型：{observation.operation_kind}\n"
            f"结果：{observation.content}"
        )
        _append_if_budget(
            selected_messages,
            omitted_items,
            role="user",
            content=content,
            source_type="tool_observation",
            keep_reason=_observation_keep_reason(observation),
            max_context_tokens=request.max_context_tokens - current_user_message.approx_tokens,
            omit_summary=f"{observation.tool_name}: {_short(observation.content)}",
        )

    # RAG 资料不是越多越好。低相关资料会干扰模型，所以默认过滤掉。
    sorted_sources = sorted(rag_sources, key=lambda item: item.relevance_score, reverse=True)
    for source in sorted_sources:
        if (not request.include_low_relevance_sources) and source.relevance_score < request.rag_min_relevance:
            omitted_items.append(
                OmittedContextItem(
                    source_type="rag",
                    summary=f"{source.source_id} {source.title}",
                    approx_tokens=estimate_tokens(source.content),
                    omit_reason=f"相关性 {source.relevance_score} 低于阈值 {request.rag_min_relevance}。",
                )
            )
            continue

        # 练习二：把检索系统的 reason 一起放进上下文，
        # 让模型不仅看到资料，还看到为什么这条资料被检索出来。
        content = (
            "[RAG资料]\n"
            f"source_id：{source.source_id}\n"
            f"标题：{source.title}\n"
            f"相关性：{source.relevance_score}\n"
            f"检索原因：{source.reason or '未提供'}\n"
            f"内容：{source.content}"
        )
        _append_if_budget(
            selected_messages,
            omitted_items,
            role="user",
            content=content,
            source_type="rag",
            keep_reason="资料相关性达到阈值，可用于约束回答。",
            max_context_tokens=request.max_context_tokens - current_user_message.approx_tokens,
            omit_summary=f"{source.source_id} {source.title}",
        )

    # ---- 历史消息选择（练习一）----
    # 优先级规则：
    # 1. 含关键槽位（订单金额/购买天数/破损）的消息优先级最高，忽略远近，只要预算够就保留。
    # 2. 剩余预算再按"最近优先"保留不含关键槽位的消息。
    KEY_SLOT_KEYWORDS = ("订单金额", "购买天数", "破损")
    RECENT_PRIORITY_COUNT = 4

    recent_history = history[-request.max_history_messages :] if request.max_history_messages else []
    kept_history: list[ContextMessage] = []

    def _history_keep_reason(has_key_slot: bool) -> str:
        if has_key_slot:
            return "历史消息包含订单金额/购买天数/破损等关键槽位信息，优先级最高，忽略远近保留。"
        return "最近历史消息，帮助模型理解对话承接。"

    # 第一轮：先扫全部历史，保留所有包含关键槽位的消息（忽略远近）。
    # 第二轮：再按最近优先补充不含关键槽位的消息。
    key_slot_messages = [m for m in recent_history if any(k in m.content for k in KEY_SLOT_KEYWORDS)]
    non_key_messages = [m for m in recent_history if not any(k in m.content for k in KEY_SLOT_KEYWORDS)]
    # 不含关键槽位的部分，按从近到远排序。
    ordered_non_key = list(reversed(non_key_messages))

    def _try_keep_history(message) -> bool:
        content = f"[历史消息]\n{message.content}"
        temp_messages = selected_messages + list(reversed(kept_history))
        used_tokens = sum(item.approx_tokens for item in temp_messages) + current_user_message.approx_tokens
        remaining_tokens = request.max_context_tokens - used_tokens
        approx_tokens = estimate_tokens(content)

        if approx_tokens <= remaining_tokens:
            kept_history.append(
                ContextMessage(
                    role=message.role,
                    content=content,
                    source_type="history",
                    approx_tokens=approx_tokens,
                    keep_reason=_history_keep_reason(
                        any(k in message.content for k in KEY_SLOT_KEYWORDS)
                    ),
                )
            )
            return True
        return False

    # 第一轮：含关键槽位的消息，忽略远近，全部尝试保留。
    for message in key_slot_messages:
        if not _try_keep_history(message):
            omitted_items.append(
                OmittedContextItem(
                    source_type="history",
                    summary=_short(message.content),
                    approx_tokens=estimate_tokens(f"[历史消息]\n{message.content}"),
                    omit_reason="包含关键槽位但预算不足，优先让位给 system/当前问题/工具 observation。",
                )
            )

    # 第二轮：不含关键槽位的消息，最近 4 条优先，再补充更早的。
    for index, message in enumerate(ordered_non_key):
        if index >= RECENT_PRIORITY_COUNT:
            omitted_items.append(
                OmittedContextItem(
                    source_type="history",
                    summary=_short(message.content),
                    approx_tokens=estimate_tokens(f"[历史消息]\n{message.content}"),
                    omit_reason="不是最近消息，也不包含关键槽位信息，按价值丢弃。",
                )
            )
            continue

        if not _try_keep_history(message):
            omitted_items.append(
                OmittedContextItem(
                    source_type="history",
                    summary=_short(message.content),
                    approx_tokens=estimate_tokens(f"[历史消息]\n{message.content}"),
                    omit_reason="历史消息优先级低于当前问题、工具 observation 和 RAG，预算不足时丢弃。",
                )
            )

    # kept_history 内部是"先关键字、后最近"的顺序，这里按对话顺序反转排列。
    # 关键字消息排在历史靠后位置会更贴近对话承接，这里统一按原时序排列。
    kept_history.sort(key=lambda m: recent_history.index(
        next(h for h in recent_history if h.content == m.content.replace("[历史消息]\n", ""))
    ))
    selected_messages.extend(kept_history)
    selected_messages.append(current_user_message)

    # ---- 练习四：统计保留/丢弃的数量，供前端工作台使用 ----
    kept_counts: dict[str, int] = {
        "history": 0,
        "rag": 0,
        "tool_observation": 0,
    }
    for message in selected_messages:
        if message.source_type == "history":
            kept_counts["history"] += 1
        elif message.source_type == "rag":
            kept_counts["rag"] += 1
        elif message.source_type == "tool_observation":
            kept_counts["tool_observation"] += 1

    context_stats = ContextStats(
        history_count_kept=kept_counts["history"],
        rag_count_kept=kept_counts["rag"],
        tool_observation_count_kept=kept_counts["tool_observation"],
        omitted_count=len(omitted_items),
    )

    return ContextBuildResult(
        messages=selected_messages,
        omitted_items=omitted_items,
        total_approx_tokens=sum(item.approx_tokens for item in selected_messages),
        max_context_tokens=request.max_context_tokens,
        policy={
            "priority_order": "system_prompt > current_user > tool_observation > rag > recent_history",
            "max_history_messages": request.max_history_messages,
            "rag_min_relevance": request.rag_min_relevance,
            "include_low_relevance_sources": request.include_low_relevance_sources,
            "token_estimator": "ceil(len(text) / 2)，教学版近似值",
            "history_priority": "最近4条优先，含关键槽位的更早消息也可保留",
            "observation_priority": "成功写操作 > 失败/其他 > 普通读查询",
        },
        context_stats=context_stats,
    )


def _observation_keep_reason(observation) -> str:
    # 练习三：根据 observation 的类型生成不同的保留理由，方便学习者在 /context/preview 里看清优先级。
    if not observation.success:
        return "工具失败 observation 保留错误原因，模型需要知道为什么不能继续。"
    if observation.operation_kind == "write":
        return "成功的写操作 observation 优先级最高，因为它改变了业务状态。"
    if observation.operation_kind == "other":
        return "其他类型操作成功，价值中等，按预算保留。"
    return "普通查询 observation，价值较低，预算不足时优先被丢弃。"

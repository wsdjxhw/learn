import re

from schemas import MemoryCandidate


def extract_memory_candidates(text: str) -> list[MemoryCandidate]:
    # 这个函数负责从用户原文里提取“候选记忆”。
    # 注意：候选不等于一定保存。后面还要经过敏感信息过滤和治理规则。
    candidates: list[MemoryCandidate] = []
    normalized = text.strip()

    candidates.extend(_extract_language_instruction(normalized))
    candidates.extend(_extract_learning_preference(normalized))
    candidates.extend(_extract_like_or_dislike(normalized))
    candidates.extend(_extract_profile(normalized))
    candidates.extend(_extract_current_topic(normalized))

    return _deduplicate_candidates(candidates)


def _extract_language_instruction(text: str) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    if "中文" in text and ("以后" in text or "默认" in text or "请用" in text):
        candidates.append(
            MemoryCandidate(
                memory_type="instruction",
                key="reply_language",
                value="中文",
                source_text=text,
                confidence=0.92,
                reason="用户表达了后续回复语言偏好。",
                retention_days=None,
            )
        )
    if "英文" in text and ("以后" in text or "默认" in text or "请用" in text):
        candidates.append(
            MemoryCandidate(
                memory_type="instruction",
                key="reply_language",
                value="英文",
                source_text=text,
                confidence=0.92,
                reason="用户表达了后续回复语言偏好。",
                retention_days=None,
            )
        )
    return candidates


def _extract_learning_preference(text: str) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    if "初学者" in text or "零基础" in text or "基础不扎实" in text:
        candidates.append(
            MemoryCandidate(
                memory_type="profile",
                key="learning_level",
                value="初学者",
                source_text=text,
                confidence=0.86,
                reason="用户说明了自己的学习阶段，后续回答可以降低前置假设。",
                retention_days=365,
            )
        )
    if "就业" in text or "面试" in text or "企业级" in text:
        candidates.append(
            MemoryCandidate(
                memory_type="preference",
                key="learning_goal",
                value="偏向就业级、企业级内容",
                source_text=text,
                confidence=0.84,
                reason="用户表达了学习材料的目标和深度偏好。",
                retention_days=365,
            )
        )
    return candidates


def _extract_like_or_dislike(text: str) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    like_matches = re.findall(r"我(?:更)?喜欢([^，。！？,.!?]{1,24})", text)
    dislike_matches = re.findall(r"我不喜欢([^，。！？,.!?]{1,24})", text)

    for value in like_matches:
        clean_value = value.strip()
        if clean_value:
            candidates.append(
                MemoryCandidate(
                    memory_type="preference",
                    key=f"likes:{clean_value}",
                    value=clean_value,
                    source_text=text,
                    confidence=0.78,
                    reason="用户明确表达了喜欢的内容。",
                    retention_days=180,
                )
            )

    for value in dislike_matches:
        clean_value = value.strip()
        if clean_value:
            candidates.append(
                MemoryCandidate(
                    memory_type="preference",
                    key=f"dislikes:{clean_value}",
                    value=f"不喜欢{clean_value}",
                    source_text=text,
                    confidence=0.78,
                    reason="用户明确表达了不喜欢的内容。",
                    retention_days=180,
                )
            )

    return candidates


def _extract_profile(text: str) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    name_match = re.search(r"我叫([^，。！？,.!?]{1,12})", text)
    role_match = re.search(r"我是([^，。！？,.!?]{1,20})", text)

    if name_match:
        candidates.append(
            MemoryCandidate(
                memory_type="profile",
                key="name",
                value=name_match.group(1).strip(),
                source_text=text,
                confidence=0.88,
                reason="用户说明了自己的称呼。",
                retention_days=None,
            )
        )

    if role_match:
        role = role_match.group(1).strip()
        if role and "初学者" not in role and "零基础" not in role:
            candidates.append(
                MemoryCandidate(
                    memory_type="profile",
                    key="role",
                    value=role,
                    source_text=text,
                    confidence=0.75,
                    reason="用户说明了自己的身份或职业背景。",
                    retention_days=365,
                )
            )

    return candidates


def _extract_current_topic(text: str) -> list[MemoryCandidate]:
    # current_topic 用来演示“会过期的记忆”。
    # 用户当前学习主题通常有复用价值，但不是永久信息，所以给 90 天保留期。
    candidates: list[MemoryCandidate] = []
    for topic in ("FastAPI", "RAG", "Agent", "SQLAlchemy", "PostgreSQL"):
        if f"正在学 {topic}" in text or f"正在学习 {topic}" in text:
            candidates.append(
                MemoryCandidate(
                    memory_type="profile",
                    key="current_topic",
                    value=topic,
                    source_text=text,
                    confidence=0.82,
                    reason="用户说明了当前学习主题，后续规划学习路径时有用。",
                    retention_days=90,
                )
            )
    return candidates


def _deduplicate_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    seen: set[tuple[str, str]] = set()
    result: list[MemoryCandidate] = []
    for candidate in candidates:
        identity = (candidate.memory_type, candidate.key)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(candidate)
    return result

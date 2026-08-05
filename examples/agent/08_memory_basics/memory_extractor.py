import re

from schemas import MemoryCandidate


def extract_memory_candidates(text: str) -> list[MemoryCandidate]:
    # 这个函数演示“记忆提取”的最小工程形态。
    # 真实项目可以让模型输出结构化 JSON，再用 Pydantic 校验；本模块先用规则保证无 key 可跑。
    candidates: list[MemoryCandidate] = []
    normalized = text.strip()

    candidates.extend(_extract_language_instruction(normalized))
    candidates.extend(_extract_learning_preference(normalized))
    candidates.extend(_extract_like_or_dislike(normalized))
    candidates.extend(_extract_profile(normalized))

    return _deduplicate_candidates(candidates)


def _extract_language_instruction(text: str) -> list[MemoryCandidate]:
    # instruction 表示用户希望 Agent 以后遵守的互动方式。
    # 例如“以后请用中文回答”比“今天下雨吗”更值得成为长期记忆。
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
            )
        )
    return candidates


def _extract_like_or_dislike(text: str) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []

    # re.findall() 会按正则查找多个片段。
    # 这里故意写得保守：只提取较短的偏好短语，避免把整段聊天误存为记忆。
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
                )
            )

    return candidates


def _extract_profile(text: str) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    name_match = re.search(r"我叫([^，。！？,.!?]{1,12})", text)
    role_match = re.search(r"我是([^，。！？,.!?]{1,20})", text)
    learn_match = re.search(r"我正在学([^，。！？,.!?]{1,20})", text)

    if name_match:
        candidates.append(
            MemoryCandidate(
                memory_type="profile",
                key="name",
                value=name_match.group(1).strip(),
                source_text=text,
                confidence=0.88,
                reason="用户说明了自己的称呼。",
            )
        )

    if role_match:
        role = role_match.group(1).strip()
        # “我是 AI 应用初学者”已经会被 learning_level 规则保存。
        # 这里避免再把它误当成 role，否则初学者会困惑为什么一段话写入两条很像的画像。
        if role and "初学者" not in role and "零基础" not in role:
            candidates.append(
                MemoryCandidate(
                    memory_type="profile",
                    key="role",
                    value=role,
                    source_text=text,
                    confidence=0.75,
                    reason="用户说明了自己的身份或职业背景。",
                )
            )

    if learn_match:
        learn = learn_match.group(1).strip()
        if learn and "FastAPI" not in learn and "RAG" not in learn:
            candidates.append(
                MemoryCandidate(
                    memory_type="profile",
                    key="learning_topic",
                    value=learn,
                    source_text=text,
                    confidence=0.75,
                    reason="用户说明了自己正在学习的内容。",
                )
            )

    return candidates


def _deduplicate_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    # 同一段话可能被多个规则命中同一个 key。
    # seen 用集合记录已经保留的身份，避免返回重复候选。
    seen: set[tuple[str, str]] = set()
    result: list[MemoryCandidate] = []
    for candidate in candidates:
        identity = (candidate.memory_type, candidate.key)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(candidate)
    return result

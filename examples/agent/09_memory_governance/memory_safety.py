import re

from schemas import MemoryCandidate, MemoryRejection


SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "api_key",
        re.compile(r"\b(?:sk|sk-proj|ak)-[A-Za-z0-9_\-]{8,}\b", re.IGNORECASE),
        "疑似 API Key 或访问密钥，不能写入长期记忆。",
    ),
    (
        "password",
        re.compile(r"(密码|password|passwd|pwd)\s*(是|=|:|：)\s*\S+", re.IGNORECASE),
        "疑似密码，不能写入长期记忆。",
    ),
    (
        "id_card",
        re.compile(r"\b\d{17}[\dXx]\b"),
        "疑似身份证号，不能写入长期记忆。",
    ),
    (
        "bank_card",
        re.compile(r"\b\d{13,19}\b"),
        "疑似银行卡号或长数字凭证，不能写入长期记忆。",
    ),
    (
        "verification_code",
        re.compile(r"(验证码|code)\s*(是|=|:|：)\s*\d{4,8}", re.IGNORECASE),
        "疑似验证码，不能写入长期记忆。",
    ),
]


def screen_memory_candidates(candidates: list[MemoryCandidate]) -> tuple[list[MemoryCandidate], list[MemoryRejection]]:
    # 安全过滤要发生在入库之前。
    # 真实项目不能先保存敏感信息再说“后面会删”，因为数据库、日志、备份都可能留下痕迹。
    accepted: list[MemoryCandidate] = []
    rejected: list[MemoryRejection] = []

    for candidate in candidates:
        rejection = inspect_sensitive_text(candidate.source_text)
        if rejection is not None:
            rejected.append(rejection)
            continue

        value_rejection = inspect_sensitive_text(candidate.value)
        if value_rejection is not None:
            rejected.append(value_rejection)
            continue

        accepted.append(candidate)

    return accepted, rejected


def inspect_sensitive_text(text: str) -> MemoryRejection | None:
    # 这里是教学版敏感信息检测。
    # 生产项目通常会组合正则、分类模型、规则引擎和人工审核。
    for risk_type, pattern, reason in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return MemoryRejection(source_text=text, risk_type=risk_type, reason=reason)
    return None

import json
from typing import Any

from pydantic import ValidationError

from schemas import RefundDecision


def extract_json_object(raw_text: str) -> dict[str, Any]:
    # 第一步：先按严格 JSON 解析。
    # 如果模型真的只返回 JSON，这一步应该直接成功。
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return parsed

    # 第二步：兼容“JSON 前后夹了自然语言”的情况。
    # 这里不用字符串 split 硬切，而是使用 Python 标准库 JSONDecoder 从每一个 { 开始尝试解析。
    # 真实项目里仍然应该优先通过 prompt / response_format 要求模型只返回 JSON。
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw_text):
        if char != "{":
            continue

        try:
            candidate, _end = decoder.raw_decode(raw_text[index:])
        except json.JSONDecodeError:
            continue

        if isinstance(candidate, dict):
            return candidate

    raise ValueError("模型输出不是可解析的 JSON object。")


def parse_and_validate(raw_text: str) -> dict[str, Any]:
    # 这个函数故意分成两层：
    # 1. JSON 解析：字符串能不能变成 Python dict。
    # 2. Pydantic 校验：dict 是否符合 RefundDecision 这份输出契约。
    #
    # 很多初学者会把这两件事混在一起。
    # “能 json.loads”只说明语法像 JSON，不代表字段完整、类型正确、枚举合法。
    try:
        data = extract_json_object(raw_text)
    except ValueError as exc:
        return {
            "ok": False,
            "stage": "json_parse",
            "error": str(exc),
            "data": None,
        }

    try:
        decision = RefundDecision.model_validate(data)
    except ValidationError as exc:
        return {
            "ok": False,
            "stage": "pydantic_validation",
            "error": exc.errors(),
            "data": data,
        }

    return {
        "ok": True,
        "stage": "validated",
        "error": None,
        "data": decision.model_dump(),
    }


def compact_error(parse_result: dict[str, Any]) -> str:
    # 重试时不要把巨大的异常对象原样塞给模型。
    # 这里压缩成短错误，方便模型知道要修什么，也方便日志查看。
    if parse_result["stage"] == "json_parse":
        return str(parse_result["error"])

    messages: list[str] = []
    for item in parse_result["error"]:
        location = ".".join(str(part) for part in item.get("loc", []))
        messages.append(f"{location}: {item.get('msg')}")
    return "; ".join(messages)

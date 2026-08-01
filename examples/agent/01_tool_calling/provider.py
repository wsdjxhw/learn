import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from tools import list_tool_schemas

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
PLACEHOLDER_API_KEY = "put-your-deepseek-api-key-here"

# provider.py 负责“模型决策层”。
# Java 类比：它类似一个调用外部 AI 服务的 Service。
# main.py 不直接写 DeepSeek 调用细节，只关心 provider 返回的决策结果。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
    # 配置可以来自当前目录的 .env，也可以来自系统环境变量。
    # 如果用户还没填真实 key，就返回 None，让程序进入 mock 模式。
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        return None
    return api_key


def get_model_name() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def get_provider_name() -> str:
    if get_api_key():
        return "deepseek"
    return "mock"


def _extract_first_number(text: str, default: float) -> float:
    # 正则表达式用于从一句中文里提取数字。
    # 例如“单价 12.5 元买 3 个”里可以提取到 12.5 和 3。
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return default
    return float(match.group())


def _extract_numbers(text: str) -> list[float]:
    # findall 会返回所有匹配到的数字字符串。
    # 列表推导式把字符串数字转成 float，方便后面计算订单金额。
    return [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text)]


def generate_mock_decision(user_message: str) -> dict[str, Any]:
    # mock 决策模拟“模型看完用户问题后，决定是否调用工具”。
    # 它不是智能模型，只是用关键词规则帮助学习者看懂完整链路。
    city_names = ["北京", "上海", "深圳", "广州", "新加坡"]
    for city in city_names:
        if city in user_message and ("天气" in user_message or "温度" in user_message or "下雨" in user_message):
            return {
                "type": "tool_call",
                "tool_name": "get_weather",
                "arguments": {"city": city},
                "reason": "用户在询问城市天气，需要调用天气工具拿到结构化结果。",
            }

    if "订单" in user_message or "总价" in user_message or "优惠" in user_message:
        numbers = _extract_numbers(user_message)
        item_price = numbers[0] if len(numbers) >= 1 else _extract_first_number(user_message, 10)
        quantity = int(numbers[1]) if len(numbers) >= 2 else 1

        discount_code = "NONE"
        if "SAVE20" in user_message.upper() or "八折" in user_message:
            discount_code = "SAVE20"
        elif "SAVE10" in user_message.upper() or "九折" in user_message:
            discount_code = "SAVE10"

        return {
            "type": "tool_call",
            "tool_name": "calculate_order_total",
            "arguments": {
                "item_price": item_price,
                "quantity": quantity,
                "discount_code": discount_code,
            },
            "reason": "用户在询问订单金额，需要调用计算工具避免口算错误。",
        }

    policy_keywords = ["报销", "退款", "假期", "密码"]
    for keyword in policy_keywords:
        if keyword in user_message:
            return {
                "type": "tool_call",
                "tool_name": "search_policy",
                "arguments": {"keyword": keyword},
                "reason": "用户在询问制度规则，需要调用制度检索工具查资料。",
            }

    return {
        "type": "answer",
        "answer": "这个问题不需要工具。我可以直接回答：工具调用适合处理查数据、算金额、检索资料这类需要外部能力的问题。",
        "reason": "用户没有提出需要查询、计算或检索的任务。",
    }


def generate_deepseek_decision(user_message: str, system_prompt: str) -> dict[str, Any]:
    # 真实模型工具调用的第一步：把工具 schema 传给模型。
    # 模型会根据用户问题判断是直接回答，还是返回 tool_calls。
    client = OpenAI(
        api_key=get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        tools=list_tool_schemas(),
        tool_choice="auto",
        stream=False,
    )

    message = response.choices[0].message
    if not message.tool_calls:
        return {
            "type": "answer",
            "answer": message.content or "",
            "reason": "模型判断不需要调用工具。",
        }

    # 教学版只处理第一个工具调用。
    # 多工具、多轮循环会放在下一个 Agent Loop 模块。
    tool_call = message.tool_calls[0]
    try:
        arguments = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError as exc:
        # 真实模型正常会返回 JSON 字符串，但后端仍然不能盲目信任。
        # 这里把解析失败转换成直接回答，避免接口因为模型输出格式问题而崩溃。
        return {
            "type": "answer",
            "answer": f"模型返回了工具调用，但工具参数不是合法 JSON：{exc}",
            "reason": "工具参数解析失败，后端拒绝执行工具。",
        }

    return {
        "type": "tool_call",
        "tool_call_id": tool_call.id,
        "tool_name": tool_call.function.name,
        "arguments": arguments,
        "reason": "模型返回了 tool_calls，说明它希望后端执行这个工具。",
    }


def decide_next_action(
    user_message: str,
    system_prompt: str,
    allow_tool: bool,
) -> dict[str, Any]:
    # allow_tool 是请求体传来的开关。
    # 它能帮助学习者对比“允许工具”和“不允许工具”时返回结果有什么不同。
    if not allow_tool:
        return {
            "type": "answer",
            "answer": "当前请求关闭了工具调用，所以我只能直接回答，不能查询天气、计算订单或检索制度。",
            "reason": "allow_tool=false，后端主动禁止工具调用。",
        }

    if get_provider_name() == "deepseek":
        return generate_deepseek_decision(user_message=user_message, system_prompt=system_prompt)

    return generate_mock_decision(user_message=user_message)


def generate_mock_final_answer(
    user_message: str,
    decision: dict[str, Any],
    tool_output: dict[str, Any],
) -> str:
    # 工具执行完成后，还需要把结构化结果整理成人能读懂的回答。
    # 真实模型会根据 tool message 生成自然语言；mock 模式下我们手写一段稳定回复。
    if not tool_output["ok"]:
        return f"我尝试调用工具 {decision['tool_name']}，但执行失败：{tool_output['error']}"

    result = tool_output["result"]
    tool_name = decision["tool_name"]

    if tool_name == "get_weather":
        return (
            f"{result['city']} 当前教学版天气：{result['temperature']} 摄氏度，"
            f"{result['condition']}。建议：{result['advice']}"
        )

    if tool_name == "calculate_order_total":
        return (
            f"订单原价 {result['original_total']} 元，优惠 {result['discount_amount']} 元，"
            f"最终应付 {result['final_total']} 元。"
        )

    if tool_name == "search_policy":
        first_match = result["matches"][0]
        return (
            f"我查到和“{result['query']}”相关的制度：{first_match['content']} "
            f"来源：{first_match['source']}。"
        )

    return f"工具已经执行完成，结果是：{result}。用户原始问题：{user_message}"


def generate_final_answer(
    user_message: str,
    system_prompt: str,
    decision: dict[str, Any],
    tool_output: dict[str, Any],
) -> str:
    # 为了让无 key 情况也能跑通，mock 模式直接生成最终回答。
    # 即使有 key，如果工具失败，也先返回可读错误，避免再把错误交给模型导致初学者难排查。
    if get_provider_name() != "deepseek" or not tool_output["ok"]:
        return generate_mock_final_answer(
            user_message=user_message,
            decision=decision,
            tool_output=tool_output,
        )

    client = OpenAI(
        api_key=get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": decision.get("tool_call_id", "teaching-tool-call"),
                        "type": "function",
                        "function": {
                            "name": decision["tool_name"],
                            "arguments": json.dumps(decision["arguments"], ensure_ascii=False),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": decision.get("tool_call_id", "teaching-tool-call"),
                "content": json.dumps(tool_output["result"], ensure_ascii=False),
            },
        ],
        stream=False,
    )
    return response.choices[0].message.content or ""

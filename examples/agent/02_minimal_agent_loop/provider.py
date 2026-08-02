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
DEFAULT_MAX_STEPS = 3

# provider.py 负责“模型决策层”。
# Java 类比：它类似一个调用外部 AI 服务的 Service。
# 这个模块需要学习真实 Agent Loop，所以 provider 同时支持：
# 1. 有 DEEPSEEK_API_KEY 时，调用真实 DeepSeek 工具调用；
# 2. 没有 key 时，自动走 mock，保证初学者仍然能跑通完整流程。
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def get_api_key() -> str | None:
    # 配置可以来自当前目录 .env，也可以来自系统环境变量。
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


def get_default_max_steps() -> int:
    # 环境变量读出来一定是字符串，所以要手动转成 int。
    # 如果 .env 写错，比如 DEFAULT_MAX_STEPS=abc，就回退到默认值，避免服务启动失败。
    raw_value = os.getenv("DEFAULT_MAX_STEPS", str(DEFAULT_MAX_STEPS))
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_MAX_STEPS

    # 即使 .env 写了很大的数字，教学示例也限制在 1 到 10 之间。
    # Agent Loop 必须有边界，否则真实模型调用可能反复消耗费用。
    return max(1, min(value, 10))


def _extract_numbers(text: str) -> list[float]:
    # 正则用于从自然语言里提取数字。
    # 例如“单价 12.5 元买 3 个”会得到 [12.5, 3.0]。
    return [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text)]


def _has_successful_tool(observations: list[dict[str, Any]], tool_name: str) -> bool:
    # observations 是前面每轮工具执行后的结果列表。
    # any(...) 表示只要有一条 observation 满足条件，就返回 True。
    return any(
        observation["tool_name"] == tool_name and observation["output"].get("ok")
        for observation in observations
    )


def _last_observation_failed(observations: list[dict[str, Any]]) -> bool:
    if not observations:
        return False
    return not observations[-1]["output"].get("ok")


def _build_mock_tool_plan(user_message: str) -> list[dict[str, Any]]:
    # 这个函数模拟“模型根据用户目标拆出需要调用的工具”。
    # 它只在没有 DeepSeek key 时使用，目的是保证无 key 也能学习 Agent Loop。
    plan: list[dict[str, Any]] = []

    city_names = ["北京", "上海", "深圳", "广州", "新加坡", "火星"]
    for city in city_names:
        if city in user_message and any(word in user_message for word in ["天气", "温度", "下雨", "出门"]):
            plan.append(
                {
                    "tool_name": "get_weather",
                    "arguments": {"city": city},
                    "reason": "用户问题包含城市和天气意图，需要先查询天气。",
                }
            )
            break

    if any(word in user_message for word in ["订单", "总价", "优惠", "多少钱"]):
        numbers = _extract_numbers(user_message)
        item_price = numbers[0] if len(numbers) >= 1 else 10
        quantity = int(numbers[1]) if len(numbers) >= 2 else 1
        discount_code = "NONE"
        if "SAVE20" in user_message.upper() or "八折" in user_message:
            discount_code = "SAVE20"
        elif "SAVE10" in user_message.upper() or "九折" in user_message:
            discount_code = "SAVE10"
        plan.append(
            {
                "tool_name": "calculate_order_total",
                "arguments": {
                    "item_price": item_price,
                    "quantity": quantity,
                    "discount_code": discount_code,
                },
                "reason": "用户问题涉及金额计算，需要调用计算工具避免口算错误。",
            }
        )

    for keyword in ["报销", "退款", "假期", "密码"]:
        if keyword in user_message:
            plan.append(
                {
                    "tool_name": "search_policy",
                    "arguments": {"keyword": keyword},
                    "reason": "用户问题涉及制度规则，需要调用检索工具获得依据。",
                }
            )
            break

    return plan


def build_final_answer(user_message: str, observations: list[dict[str, Any]]) -> str:
    # mock 模式下，最终回答不是简单把工具 JSON 原样丢给用户。
    # Agent 要把 observation 整理成人能读懂的结论。
    if not observations:
        return "这个问题不需要调用工具，可以直接回答：Agent Loop 的核心是反复观察上一步结果，再决定下一步。"

    last_output = observations[-1]["output"]
    if not last_output.get("ok"):
        return f"工具执行失败，所以我停止继续调用工具。失败原因：{last_output.get('error')}"

    parts: list[str] = []
    for observation in observations:
        output = observation["output"]
        if not output.get("ok"):
            parts.append(f"{observation['tool_name']} 失败：{output.get('error')}")
            continue

        result = output["result"]
        if observation["tool_name"] == "get_weather":
            parts.append(
                f"{result['city']}天气：{result['temperature']} 度，{result['condition']}，{result['advice']}"
            )
        elif observation["tool_name"] == "calculate_order_total":
            parts.append(
                f"订单原价 {result['original_total']} 元，优惠后 {result['final_total']} 元。"
            )
        elif observation["tool_name"] == "search_policy":
            parts.append(f"{result['keyword']}制度：{result['content']}")

    return "；".join(parts)


def generate_mock_decision(
    user_message: str,
    observations: list[dict[str, Any]],
    allow_tools: bool,
) -> dict[str, Any]:
    # mock 决策用于无 key 情况。
    # 它不是智能模型，只是用关键词规则帮助学习者看懂完整循环链路。
    if not allow_tools:
        return {
            "type": "final_answer",
            "thought": "本次请求关闭了工具调用，不能进入动作阶段。",
            "answer": "当前 allow_tools=false，所以我只能直接回答，不能查询天气、计算订单或检索制度。",
        }

    if _last_observation_failed(observations):
        return {
            "type": "final_answer",
            "thought": "上一轮工具失败。继续盲目调用可能制造更多错误，所以先停止。",
            "answer": build_final_answer(user_message, observations),
        }

    # 这个特殊输入用于观察 max_steps 的保护效果。
    # 如果没有最大步数，Agent 可能一直以为“还要继续查”，导致无限循环。
    if "循环测试" in user_message:
        return {
            "type": "tool_call",
            "thought": "用户触发了循环测试，我会持续选择同一个工具，直到 Agent Loop 的 max_steps 截停。",
            "tool_name": "search_policy",
            "arguments": {"keyword": "报销"},
            "reason": "用于演示为什么必须限制 Agent 最大执行步数。",
        }

    plan = _build_mock_tool_plan(user_message)
    for item in plan:
        if not _has_successful_tool(observations, item["tool_name"]):
            return {
                "type": "tool_call",
                "thought": item["reason"],
                "tool_name": item["tool_name"],
                "arguments": item["arguments"],
                "reason": item["reason"],
            }

    return {
        "type": "final_answer",
        "thought": "需要的工具都已经执行完，下一步应该整理 observation，返回最终回答。",
        "answer": build_final_answer(user_message, observations),
    }


def _build_deepseek_messages(
    user_message: str,
    system_prompt: str,
    observations: list[dict[str, Any]],
) -> list[dict[str, str]]:
    # 真实模型每一轮都要看到：
    # 1. system prompt：约束 Agent 如何工作；
    # 2. 用户目标：这次 run 要完成什么；
    # 3. 已有 observation：前几轮工具执行结果。
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": f"用户目标：{user_message}",
        },
    ]

    if observations:
        # observation 用 JSON 传给模型，模型更容易看清工具名、参数、成功状态和结果。
        # ensure_ascii=False 可以保留中文，不会把中文转成 \uXXXX。
        messages.append(
            {
                "role": "user",
                "content": "目前已经执行过的工具 observation：\n"
                + json.dumps(observations, ensure_ascii=False, indent=2)
                + "\n请根据这些 observation 判断下一步：如果信息足够就直接最终回答；如果还缺信息才继续调用工具。",
            }
        )

    return messages


def generate_deepseek_decision(
    user_message: str,
    system_prompt: str,
    observations: list[dict[str, Any]],
    allow_tools: bool,
) -> dict[str, Any]:
    # 真实模型决策：每一轮都把用户目标和已有 observation 发给 DeepSeek。
    # DeepSeek 要么返回普通文本，表示可以 final_answer；要么返回 tool_calls，表示需要后端执行工具。
    client = OpenAI(
        api_key=get_api_key(),
        base_url=DEEPSEEK_BASE_URL,
    )

    kwargs: dict[str, Any] = {
        "model": get_model_name(),
        "messages": _build_deepseek_messages(
            user_message=user_message,
            system_prompt=system_prompt,
            observations=observations,
        ),
        "stream": False,
    }

    if allow_tools:
        kwargs["tools"] = list_tool_schemas()
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
    message = response.choices[0].message

    if message.tool_calls:
        # 教学版 Agent Loop 每一轮只执行一个工具。
        # 如果真实模型一次返回多个工具调用，这里先取第一个；多工具并行/编排放到下一个模块。
        tool_call = message.tool_calls[0]
        try:
            arguments = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError as exc:
            return {
                "type": "final_answer",
                "thought": "模型返回了工具调用，但工具参数不是合法 JSON，后端拒绝执行。",
                "answer": f"模型返回了工具调用，但参数解析失败：{exc}",
            }

        return {
            "type": "tool_call",
            "thought": "真实模型判断还需要调用工具。",
            "tool_name": tool_call.function.name,
            "arguments": arguments,
            "reason": "DeepSeek 返回了 tool_calls，说明它希望后端执行这个工具。",
        }

    return {
        "type": "final_answer",
        "thought": "真实模型判断信息已经足够，可以直接回答。",
        "answer": message.content or "",
    }


def decide_next_action(
    user_message: str,
    system_prompt: str,
    observations: list[dict[str, Any]],
    allow_tools: bool,
) -> dict[str, Any]:
    # 这是 Agent Loop 每一轮调用的统一入口。
    # agent_loop.py 不需要知道当前是真实 DeepSeek 还是 mock，只关心返回的决策结构。
    if get_provider_name() == "deepseek":
        try:
            return generate_deepseek_decision(
                user_message=user_message,
                system_prompt=system_prompt,
                observations=observations,
                allow_tools=allow_tools,
            )
        except Exception as exc:
            # 真实模型调用可能因为网络、key、模型名、服务端错误失败。
            # 教学示例不让接口直接崩溃，而是把失败解释成最终回答。
            return {
                "type": "final_answer",
                "thought": "真实模型调用失败，后端停止 Agent Loop。",
                "answer": f"DeepSeek 调用失败：{exc}",
            }

    return generate_mock_decision(
        user_message=user_message,
        observations=observations,
        allow_tools=allow_tools,
    )

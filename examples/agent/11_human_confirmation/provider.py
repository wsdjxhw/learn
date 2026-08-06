import json
from typing import Any

from openai import OpenAI

from settings import get_settings


def get_provider_name() -> str:
    settings = get_settings()
    return "deepseek" if settings.model_mode == "deepseek" else "mock"


def decide_next_action(
    user_message: str,
    tool_schemas: list[dict[str, Any]],
    auth_user_id: str,
    allow_tool: bool,
) -> dict[str, Any]:
    # provider.py 是模型决策层。
    # main.py 不应该关心模型怎么判断工具，只关心它返回的是 answer 还是 tool_call。
    settings = get_settings()
    if not allow_tool:
        return {"type": "answer", "answer": f"已关闭工具调用，我只能根据问题直接回答：{user_message}"}

    if settings.model_mode == "deepseek":
        return _decide_with_deepseek(user_message, tool_schemas)

    return _decide_with_mock(user_message, tool_schemas, auth_user_id)


def generate_final_answer(user_message: str, tool_output: dict[str, Any]) -> str:
    # 工具执行后，还需要把结构化工具结果组织成用户能看懂的回答。
    # mock 模式直接拼接；真实项目可能再次调用模型生成自然语言总结。
    settings = get_settings()
    if settings.model_mode == "deepseek":
        return _generate_deepseek_final_answer(user_message, tool_output)

    if not tool_output.get("ok"):
        return f"工具执行失败：{tool_output.get('error')}。请检查参数或权限。"

    return f"已根据授权工具返回结果：{tool_output['result']}"


def _decide_with_mock(user_message: str, tool_schemas: list[dict[str, Any]], auth_user_id: str) -> dict[str, Any]:
    # mock 决策用关键词模拟模型选工具。
    # 重点不是做聪明模型，而是让学习者稳定观察“选工具 -> 权限检查 -> 执行 -> 审计”的链路。
    available_names = {item["function"]["name"] for item in tool_schemas}

    def can_use(name: str) -> bool:
        return name in available_names

    if any(word in user_message for word in ["审计", "日志"]) and can_use("list_audit_logs"):
        return {"type": "tool", "tool_name": "list_audit_logs", "arguments": {"limit": 10}}

    if any(word in user_message for word in ["套餐", "升级", "降级", "企业版"]) and can_use("update_user_plan"):
        return {
            "type": "tool",
            "tool_name": "update_user_plan",
            "arguments": {"target_user_id": auth_user_id, "new_plan": "pro", "reason": "用户请求修改套餐"},
        }

    if any(word in user_message for word in ["工单", "客服", "反馈", "故障"]) and can_use("create_support_ticket"):
        return {
            "type": "tool",
            "tool_name": "create_support_ticket",
            "arguments": {"target_user_id": auth_user_id, "title": user_message[:40], "priority": "normal"},
        }

    if any(word in user_message for word in ["记忆", "偏好", "画像"]) and can_use("get_memory_summary"):
        return {
            "type": "tool",
            "tool_name": "get_memory_summary",
            "arguments": {"target_user_id": auth_user_id, "topic": "偏好"},
        }

    if any(word in user_message for word in ["报销", "假期", "密码", "退款", "制度"]) and can_use("search_company_policy"):
        keyword = "报销"
        for candidate in ["报销", "假期", "密码", "退款"]:
            if candidate in user_message:
                keyword = candidate
                break
        return {"type": "tool", "tool_name": "search_company_policy", "arguments": {"keyword": keyword}}

    return {
        "type": "answer",
        "answer": "当前角色没有合适的可用工具，或问题不需要工具。我会先给出普通回答。",
    }


def _decide_with_deepseek(user_message: str, tool_schemas: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        temperature=0,
        tools=tool_schemas,
        tool_choice="auto",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是教学用 Agent。只能从提供的工具中选择。"
                    "如果没有合适工具，就直接回答。不要编造工具名。"
                ),
            },
            {"role": "user", "content": user_message},
        ],
    )

    message = response.choices[0].message
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        return {
            "type": "tool",
            "tool_name": tool_call.function.name,
            "arguments": json.loads(tool_call.function.arguments or "{}"),
        }

    return {"type": "answer", "answer": message.content or "没有可用工具，且模型没有生成回答。"}


def _generate_deepseek_final_answer(user_message: str, tool_output: dict[str, Any]) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "你负责把工具返回的 JSON 结果整理成简洁中文回答。不要隐藏工具失败原因。",
            },
            {"role": "user", "content": f"用户问题：{user_message}\n工具结果：{json.dumps(tool_output, ensure_ascii=False)}"},
        ],
    )
    return response.choices[0].message.content or ""

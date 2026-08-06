import json
from typing import Any

from openai import OpenAI

from settings import get_settings


def get_provider_name() -> str:
    settings = get_settings()
    return "deepseek" if settings.model_mode == "deepseek" else "mock"


# mock 模式下判断“要不要检索知识库”的触发词。
# 真实模型靠语义理解判断，mock 模型靠关键词近似判断，目的是让你稳定观察到同一条链路。
_KNOWLEDGE_MARKERS = ["报销", "请假", "考勤", "制度", "流程", "政策", "手册", "规定", "福利", "休假", "工资", "培训", "出差", "保险"]
# 注意同时收录“是什么”和“什么是”，否则“什么是黑洞”这种问句不会触发检索。
_ASK_MARKERS = ["是什么", "什么是", "有哪些", "怎么办", "如何", "怎么", "能不能", "为什么"]


def decide_next_action(
    user_message: str,
    tool_schemas: list[dict[str, Any]],
    allow_tool: bool,
) -> dict[str, Any]:
    # provider.py 是模型决策层。
    # main.py 不关心模型怎么判断，只关心它返回的是 answer 还是 tool_call。
    if not allow_tool:
        # allow_tool=false 时强制不允许检索，用来对比“能检索”和“不能检索”的回答差异。
        return {
            "type": "answer",
            "answer": "本轮已关闭知识库检索工具。我不知道知识库内容，只能泛泛回答，不能给出带依据的准确答案。",
        }

    settings = get_settings()
    if settings.model_mode == "deepseek":
        return _decide_with_deepseek(user_message, tool_schemas)

    return _decide_with_mock(user_message, tool_schemas)


def generate_final_answer(user_message: str, tool_output: dict[str, Any]) -> str:
    # 工具执行后，还需要把结构化检索结果组织成用户能看懂的回答。
    # 本模块的验收标准之一就是“检索不到资料时说明不足”，所以两种模式都要处理 count=0。
    settings = get_settings()
    if settings.model_mode == "deepseek":
        return _generate_deepseek_final_answer(user_message, tool_output)

    return _generate_mock_final_answer(user_message, tool_output)


def _decide_with_mock(user_message: str, tool_schemas: list[dict[str, Any]]) -> dict[str, Any]:
    # mock 决策用关键词模拟模型选工具。
    # 重点不是做聪明模型，而是让学习者稳定观察“判断要不要检索 -> 调用工具 -> 拿 sources -> 组织回答”。
    available_names = {item["function"]["name"] for item in tool_schemas}
    if "search_documents" not in available_names:
        return {"type": "answer", "answer": "当前没有可用的知识库检索工具。"}

    # 触发检索的条件：问题里出现了知识类话题词，或者是一个明确的“问知识”句式。
    hit_marker = any(marker in user_message for marker in _KNOWLEDGE_MARKERS)
    hit_ask = any(marker in user_message for marker in _ASK_MARKERS)

    if hit_marker or hit_ask:
        return {
            "type": "tool",
            "tool_name": "search_documents",
            # mock 模式下直接把用户问题原文当作检索词。
            # retriever.py 用中文 bigram 分词，所以整句也能命中相关片段。
            "arguments": {"query": user_message, "top_k": 3},
        }

    return {
        "type": "answer",
        "answer": "这个问题不涉及企业知识库内容，我可以直接回答，不需要调用检索工具。",
    }


def _generate_mock_final_answer(user_message: str, tool_output: dict[str, Any]) -> str:
    # mock 模式不做真正的语义总结，而是“诚实展示依据”：
    # - 有资料：引用最相关的来源，告诉用户回答依据来自哪篇文档。
    # - 没资料：明确说资料不足，绝不编造。这是 RAG Agent 最重要的一条底线。
    if not tool_output.get("ok"):
        return f"检索工具执行失败：{tool_output.get('error')}"

    results = tool_output.get("results", [])
    if tool_output.get("count", 0) == 0:
        note = tool_output.get("note", "没有检索到相关资料")
        return (
            f"知识库中没有检索到与“{user_message}”相关的资料（{note}）。\n"
            "为了避免编造，我不能凭想象回答这个问题。建议先补充相关文档，"
            "或者换个更接近知识库原文的说法再问一次。"
        )

    top = results[0]
    excerpt = top["content"][:80]
    source_titles = "、".join(sorted({item["document_title"] for item in results}))
    return (
        f"基于知识库检索结果，我可以回答这个问题。\n"
        f"最相关的资料来自《{top['document_title']}》第 {top['chunk_index']} 段：\n"
        f"{excerpt}...\n\n"
        f"本次回答共引用 {len(results)} 条 sources，来源文档：{source_titles}。"
    )


def _decide_with_deepseek(user_message: str, tool_schemas: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("MODEL_MODE=deepseek 时必须配置 DEEPSEEK_API_KEY。")

    # openai 包通过 OpenAI 兼容协议调用 DeepSeek。
    # base_url 指向 DeepSeek 的接口地址，工具选择用官方 tools / tool_choice 参数。
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
                    "你是企业知识库 Agent。当用户的问题涉及制度、流程、政策、规定等企业知识时，"
                    "调用 search_documents 检索资料；其他日常问题可以直接回答。只能使用提供的工具，不要编造工具名。"
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
            # 模型返回的 arguments 是 JSON 字符串，要解析成 dict 才能传给工具。
            "arguments": json.loads(tool_call.function.arguments or "{}"),
        }

    return {"type": "answer", "answer": message.content or "模型没有生成回答。"}


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
                "content": (
                    "你是企业知识库问答助手。只能基于用户提供的检索结果回答；"
                    "如果检索结果为空，明确说明知识库资料不足，不要编造。"
                    "回答末尾列出引用到的来源文档标题。"
                ),
            },
            {
                "role": "user",
                "content": f"用户问题：{user_message}\n检索结果：{json.dumps(tool_output, ensure_ascii=False)}",
            },
        ],
    )
    return response.choices[0].message.content or ""

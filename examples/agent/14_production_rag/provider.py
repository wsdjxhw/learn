"""
provider.py - 模型服务层

职责：对外提供两个能力：
1. decide：判断“这个问题要不要检索知识库”；
2. answer：基于检索结果生成最终回答。
本模块的模型入口是 run_agent_chat()，内部按 MODEL_MODE 走 mock 或 DeepSeek。

为什么要有 provider 层？
1. 屏蔽差异：接口层 / Agent 层不用关心“现在是假模型还是真模型”，
   反正都调用 run_agent_chat()。换模型只改这一个文件。
2. 可测试：mock 模式下不依赖网络和 key，任何环境都能跑通并断言结果。
3. 可升级：真实项目里这里可以接任意模型（OpenAI / DeepSeek / 本地模型），
   对外暴露的接口签名不变。

真实模式调用 DeepSeek：
用 openai 包的 OpenAI 兼容协议。DeepSeek 提供了 OpenAI 兼容的 HTTP 接口，
所以只需改 base_url 和 api_key，客户端 API 和 OpenAI 完全一致。
"""
import json

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from chunker import to_bigrams
from models import Document, Chunk
from permissions import User
from rag import run_rag_search
from retriever import _visible_documents, bigram_overlap
from settings import settings
from tool_registry import get_tools
from tools import execute_search_documents

# 系统提示词。它决定 Agent 的行为边界：
# 什么时候检索、检索不到怎么办。真实项目里系统提示词通常是独立文件（见模块 04）。
SYSTEM_PROMPT = (
    "你是企业知识库助手。当用户的问题涉及企业制度、流程、文档内容时，"
    "你必须调用 search_documents 工具检索知识库后再回答。"
    "如果检索不到相关资料，请如实说明知识库中没有相关内容，不要编造。"
)


def _decide_mock(db: Session, user: User, message: str) -> str:
    """mock 模式的检索决策，返回三态之一：
    - "idle"：问题与可见知识库完全不相关 -> 当闲聊处理，不检索；
    - "no_data"：有一点字面共现但强度不够 -> 知识型问题但库里没料，诚实说资料不足；
    - "search"：字面共现足够 -> 值得检索。

    为什么用三态而不是“检索/不检索”两态？
    真实 RAG 里“不该检索”和“该检索但没结果”是两种不同的情况：
    - 闲聊不该触发检索；
    - 知识问题检索不到，必须诚实说“资料不足”，否则会编造。
    两态逻辑会把这两种情况混成一种，回答就会出问题。

    为什么共现要 >= 2 才算值得检索？
    bigram 是相邻两字，存在大量“跨词巧合”，例如：
    问题“产品路线图的三季度规划”里，“季度规划”含 bigram “度规”，
    而员工请假制度“制度规定”也含“度规”。单个 bigram 撞上毫无意义。
    要求至少 2 个不同 bigram 共现，能过滤掉绝大多数这种巧合。
    这其实就是“相关性阈值”在决策层的最简体现。
    """
    # 注意“用户可见”四个字：权限过滤在这里也要生效，
    # 否则 bob 检索不到 alice 的私有文档，决策层却假装“知识库有内容”。
    visible = _visible_documents(db, user)
    best_overlap = 0
    for doc in visible:
        for chunk in doc.chunks:
            best_overlap = max(best_overlap, bigram_overlap(message, chunk.content))
    if best_overlap == 0:
        return "idle"
    if best_overlap < 2:
        return "no_data"
    return "search"


def _mock_answer(message: str, sources: list[dict]) -> str:
    """mock 模式的最终回答：从检索结果拼一段像样的答案。

    教学版不追求“回答质量”，只演示“带 sources 的回答长什么样”。
    真实模式下这个函数不存在，回答完全由大模型生成。
    """
    if not sources:
        # 检索不到 -> 诚实说不足，这正是 RAG 防幻觉的最后一环
        return f"知识库中暂时没有找到与“{message}”相关的资料。请补充相关文档，或换个问法试试。"

    lines = [f"根据知识库，关于“{message}”找到以下内容：", ""]
    for i, src in enumerate(sources, start=1):
        # 只截前 120 字，避免 mock 回答过长
        snippet = src["content"][:120]
        lines.append(f"{i}. 来源《{src['document_title']}》：{snippet}")
    lines.append("")
    lines.append("（以上回答依据来自知识库检索结果）")
    return "\n".join(lines)


def _deepseek_chat(db: Session, user: User, message: str) -> dict:
    """DeepSeek 模式：走一次 function calling 循环。

    完整流程（这也是真实 Agent 工具调用的最小骨架）：
    1. 把系统提示词 + 用户消息 + 工具定义发给模型；
    2. 模型决定：直接回答（content）或调用工具（tool_calls）；
    3. 如果调用工具：后端执行工具，把结果作为 role=tool 的消息回给模型；
    4. 模型基于工具结果生成最终回答。

    为什么要把工具结果回给模型？
    模型第一次回答时“看不到”检索结果，只有把工具输出喂回去，
    它才能基于这些资料组织回答。这正是 Agent 循环中“观察（observation）”的体现。
    """
    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )

    # messages 是发给模型的完整对话，注意它的结构：
    # - system：行为边界；- user：用户问题；
    # - assistant + tool：工具调用的“一问一答”回合。
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    # 第一次调用：让模型决定要不要用工具。
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        tools=get_tools(),          # 把注册表里的工具定义传给模型
        tool_choice="auto",         # auto = 模型自己决定用不用
    )
    msg = resp.choices[0].message

    # 模型没有要求调用工具 -> 直接回答，没有检索
    if not msg.tool_calls:
        return {"used_tool": False, "answer": msg.content or "", "sources": []}

    # 模型要求调用工具 -> 逐个执行，并把结果回给模型
    sources: list[dict] = []
    # 先把模型的工具调用请求本身加入对话（role=assistant + tool_calls 字段）
    messages.append({
        "role": "assistant",
        "content": None,  # 有 tool_calls 时 content 必须为 null
        "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
    })
    for tc in msg.tool_calls:
        # tc.function.name 是工具名；arguments 是模型生成的 JSON 字符串，需要解析
        arguments = json.loads(tc.function.arguments or "{}")
        # 后端执行工具（权限过滤、参数校验都在里面）
        result = execute_search_documents(db, user, arguments)
        sources = result.get("sources", [])
        # 把工具执行结果作为 role=tool 的消息回给模型
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    # 第二次调用：模型基于工具结果生成最终回答
    resp2 = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
    )
    answer = resp2.choices[0].message.content or ""
    return {"used_tool": True, "answer": answer, "sources": sources}


def run_agent_chat(db: Session, user: User, message: str) -> dict:
    """Agent 对话统一入口：决定是否检索，并生成带 sources 的回答。

    这是接口层 /agent/chat 唯一调用的模型层函数。
    返回结构固定：{"used_tool", "answer", "sources"}，
    这样前端不用关心底层是 mock 还是 DeepSeek。
    """
    if settings.model_mode != "deepseek" or not settings.deepseek_api_key:
        # ---------- mock 模式：本地规则决策 + 模板回答 ----------
        decision = _decide_mock(db, user, message)

        # 完全不相关：当闲聊处理，不触发检索
        if decision == "idle":
            return {
                "used_tool": False,
                "answer": "（mock 模式）这是一个普通问题，不需要检索知识库。",
                "sources": [],
            }

        # 知识型问题：执行检索，并带上相关性阈值。
        # min_score 的作用：检索到一堆“碰巧含查询字眼”的低分片段时，
        # 把它们挡在回答之外，避免基于无关材料编答案。
        result = run_rag_search(db, user, query=message, min_score=settings.rag_min_score)

        # 检索了但没有够格的资料（或 decision==no_data）：
        # 诚实说不足，而不是强行用低分片段回答 —— 这是 RAG 防幻觉的关键一环
        if not result.sources:
            return {
                "used_tool": decision == "search",
                "answer": f"知识库中暂时没有找到与“{message}”相关的资料。请补充相关文档，或换个问法试试。",
                "sources": [],
            }

        return {
            "used_tool": True,
            "answer": _mock_answer(message, result.sources),
            "sources": result.sources,
        }

    # ---------- DeepSeek 模式：真实 function calling ----------
    return _deepseek_chat(db, user, message)

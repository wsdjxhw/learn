"""
provider.py —— 模型提供方：mock 模式 或 真实 DeepSeek

职责：把"模型"这个黑盒抽象成两个动作——
1. decide_tool(question, role, visible_tools, feedback)：决定要不要调用工具、调哪个、传什么参数。
2. compose_answer(question, tool_result, role)：根据工具执行结果生成最终的自然语言回答。

为什么要抽象成统一的 Provider 接口？
因为 mock 和真实模型只是"实现不同"，用法完全一样。学习时用 mock
（零成本、结果确定），找工作/演示时切真实模型，代码其他地方一行不用改。

切换方式：settings.py 里的 MOCK_MODE。
- true  -> MockProvider（关键词规则，不联网）
- false -> DeepSeekProvider（openai 包 + function calling）
"""

import json
import re
from abc import ABC, abstractmethod

from openai import OpenAI

from schemas import ToolDecision
from settings import settings
from tool_registry import ToolMeta, format_status_cn, to_openai_schema


# 给模型看的系统提示词（真实项目会单独放到 prompts 文件里管理，见模块 04）
SYSTEM_PROMPT = (
    "你是企业订单管理系统的数据库助手。你可以调用工具查询和修改订单、客户数据。\n"
    "规则：\n"
    "1. 只能使用提供的工具，绝不能自己生成 SQL 去执行（除非工具是 run_sql_readonly）。\n"
    "2. 写操作（创建订单/改状态/删除订单）执行后会生成确认单，不会立即生效，"
    "你要如实告诉用户'已发起确认，等待审批'。\n"
    "3. 查询结果必须以工具返回的真实数据为准，不得编造数字。\n"
    "4. 如果工具返回权限不足或失败，要如实说明原因，不要假装成功。\n"
    "5. 用户问题不涉及数据库时，直接回答即可，不要强行调用工具。"
)


class BaseProvider(ABC):
    """模型提供方的抽象基类。mock 和 DeepSeek 都实现这两个方法。"""

    @abstractmethod
    def decide_tool(
        self,
        question: str,
        role: str,
        visible_tools: list[ToolMeta],
        feedback: object | None = None,
    ) -> ToolDecision | None:
        """判断要不要调用工具。返回 ToolDecision 或 None（直接回答）。"""

    @abstractmethod
    def compose_answer(self, question: str, tool_result: object | None, role: str) -> str:
        """根据工具执行结果，生成给用户的最终回答。"""


# ===================== Mock 模式（无 API Key 也能跑） =====================

# 中文状态关键词 -> 英文状态，供 mock 从用户问题里猜状态
STATUS_CN_MAP = {
    "发货": "shipped",
    "完成": "completed",
    "取消": "cancelled",
    "付款": "paid",
    "已付": "paid",
}


class MockProvider(BaseProvider):
    """教学版假模型：用关键词规则"假装"模型决策。

    它不是真的 AI，而是把"哪些问题该调哪个工具"写死成规则。
    优点：零成本、结果可预测、能稳定演示流程。
    局限：不能理解复杂话术，参数提取很粗糙（真实场景由 DeepSeek 负责）。
    """

    def decide_tool(self, question, role, visible_tools, feedback=None):
        # 如果上一轮工具已经失败/被拦，mock 选择放弃，直接进入回答环节
        if feedback is not None and getattr(feedback, "status", "") in ("failed", "blocked"):
            return None

        q = question.lower()

        # --- 写操作（优先判断，因为它们更危险） ---
        if any(k in q for k in ["删除订单", "删掉订单", "删除"]):
            oid = _extract_order_id(question)
            if oid:
                return ToolDecision(tool_name="delete_order", args={"order_id": oid})

        if any(k in q for k in ["创建订单", "新建订单", "下单", "新增订单", "添加订单", "买一"]):
            return ToolDecision(
                tool_name="create_order",
                args={
                    "customer_id": _extract_customer_id(question) or 1,
                    "product_name": _extract_product(question) or "默认商品",
                    "amount": _extract_amount(question) or 100.0,
                },
            )

        if any(k in q for k in ["发货", "改状态", "更新状态", "状态改为", "状态改成"]):
            oid = _extract_order_id(question)
            if oid:
                return ToolDecision(
                    tool_name="update_order_status",
                    args={"order_id": oid, "new_status": _extract_status(question)},
                )

        # --- 统计 ---
        if any(k in q for k in ["统计", "总计", "一共", "总额", "汇总", "多少单", "哪个城市"]):
            group_by = "city" if "城市" in q else "status"
            return ToolDecision(tool_name="query_order_stats", args={"group_by": group_by})

        # --- 只读 SQL（进阶工具） ---
        if re.search(r"\bselect\b", q):
            return ToolDecision(tool_name="run_sql_readonly", args={"sql": _extract_sql(question)})

        # --- 订单查询 ---
        if "订单" in q:
            args = {}
            for cn, en in STATUS_CN_MAP.items():
                if cn in q:
                    args["status"] = en
                    break
            return ToolDecision(tool_name="query_orders", args=args)

        # --- 客户查询 ---
        if any(k in q for k in ["客户", "谁买", "北京", "上海", "深圳", "广州"]):
            args = {}
            for city in ["北京", "上海", "深圳", "广州"]:
                if city in q:
                    args["city"] = city
                    break
            if "vip" in q:
                args["tier"] = "vip"
            return ToolDecision(tool_name="query_customers", args=args)

        return None  # 不涉及数据库，直接回答

    def compose_answer(self, question, tool_result, role):
        if tool_result is None:
            return ("这个问题不涉及订单/客户数据，我没有调用工具。\n"
                    "你可以试试问我：'统计各状态的订单数量'、'查询北京的客户'、'给订单3发货'。")

        if tool_result.status == "awaiting_confirmation":
            return (f"好的，我已发起写操作，并生成确认单 #{tool_result.confirmation_id}。\n"
                    "注意：写操作不会直接执行！需要审批人批准后才会真正写入数据库。")

        if tool_result.status == "blocked":
            return f"抱歉，当前账号（{role}）没有权限执行这个操作：{tool_result.message}"

        if tool_result.status == "failed":
            return f"操作没有完成：{tool_result.message}"

        # --- success：根据工具返回的数据构造回答 ---
        data = tool_result.data or {}
        if "rows" in data:  # 查询类工具
            lines = _format_rows(data.get("rows", []), data.get("group_by"))
            head = f"查询完成，共 {data['count']} 条记录："
            return head + "\n" + "\n".join(lines) if lines else head + "（无记录）"
        if "order_id" in data:  # 写操作成功
            return data.get("message", "操作成功")
        return tool_result.message


def _extract_order_id(text: str) -> int | None:
    m = re.search(r"订单\s*[#号]?\s*(\d+)", text)
    return int(m.group(1)) if m else None


def _extract_customer_id(text: str) -> int | None:
    m = re.search(r"客户\s*[#号]?\s*(\d+)", text)
    return int(m.group(1)) if m else None


def _extract_amount(text: str) -> float | None:
    m = re.search(r"金额\D*(\d+(?:\.\d+)?)", text) or re.search(r"(\d+(?:\.\d+)?)\s*元", text)
    return float(m.group(1)) if m else None


def _extract_product(text: str) -> str | None:
    # (?:一?[台个只部双])? 会吃掉"一台/个/只"这样的量词，剩下的才是商品名
    m = re.search(r"买(?:一?[台个只部双])?([一-龥]{2,12})(?=[，,、。]|$)", text)
    return m.group(1) if m else None


def _extract_status(text: str) -> str:
    for cn, en in STATUS_CN_MAP.items():
        if cn in text:
            return en
    return "shipped"


def _extract_sql(text: str) -> str:
    m = re.search(r"(select\b.*)", text, re.I)
    return m.group(1).strip().rstrip("。，,；;") if m else "SELECT 1"


def _format_rows(rows: list[dict], group_by: str | None) -> list[str]:
    """把查询结果转成一行行易读的中文。"""
    lines = []
    for r in rows:
        if group_by:  # 统计结果：按状态/城市统计
            lines.append(f"· {r[group_by]}：{r['order_count']} 单，总金额 {r['total_amount']} 元")
        else:
            parts = []
            for k, v in r.items():
                if k == "status":
                    v = format_status_cn(v)  # 状态转中文，更好读
                parts.append(f"{k}={v}")
            lines.append("· " + "，".join(parts))
    return lines


# ===================== 真实 DeepSeek 模式（需 API Key） =====================


class DeepSeekProvider(BaseProvider):
    """真实模型：通过 openai 包调用 DeepSeek，走 function calling。

    这里的关键是"工具调用"（function calling）：
    我们把工具注册表里的每个工具转成 JSON schema 传给模型（tools 参数），
    模型看到用户问题后，如果觉得需要，就会返回"我要调用某个工具，参数是 xxx"。
    然后后端执行，把结果再喂回去生成回答。这个"模型选工具"的能力，
    就是 Agent 和普通聊天接口最大的区别。
    """

    def __init__(self):
        if not settings.deepseek_api_key:
            raise RuntimeError("MOCK_MODE=false 但未配置 DEEPSEEK_API_KEY，请检查 .env")
        # OpenAI 兼容协议：只要服务商支持 OpenAI 接口格式，改 base_url 就能换模型
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model

    def decide_tool(self, question, role, visible_tools, feedback=None):
        # 把工具转成 OpenAI function calling 需要的 schema
        tool_schemas = [to_openai_schema(t) for t in visible_tools]

        content = f"（当前角色：{role}）{question}"
        if feedback is not None:  # 上一轮工具失败时给模型一个纠错提示
            content += f"\n（提醒：上一轮工具执行结果为：{format_observation(feedback)}。"
            content += "如果这个结果说明此路不通，请换一种方式或直接回答，不要重复同一个调用。）"

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            tools=tool_schemas,     # 告诉模型"你有这些工具可以用"
            tool_choice="auto",     # 让模型自己决定用不用工具
        )

        message = resp.choices[0].message
        if message.tool_calls:
            # 模型决定调用工具：解析出工具名和参数
            call = message.tool_calls[0]
            try:
                args = json.loads(call.function.arguments or "{}")
            except ValueError:
                args = {}
            return ToolDecision(tool_name=call.function.name, args=args)
        return None  # 模型决定直接回答

    def compose_answer(self, question, tool_result, role):
        if tool_result is None:
            content = f"（当前角色：{role}）请直接回答：{question}"
        else:
            content = (
                f"（当前角色：{role}）用户问题：{question}\n\n"
                f"工具执行结果：\n{format_observation(tool_result)}\n\n"
                "请根据真实数据用自然语言回答用户。如果数据不足，请如实说明。"
            )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
        return resp.choices[0].message.content or ""


def format_observation(result) -> str:
    """把工具执行结果压缩成一小段文字（observation）。

    作用：展示给前端 steps，同时作为"观察"反馈给模型。
    注意：要控制长度，不能把几百行数据全塞进去（这属于模块 06 的上下文工程）。
    """
    if result.status == "success":
        data = result.data or {}
        if "rows" in data:
            rows = data.get("rows", [])
            return f"查询成功，共 {data['count']} 条记录，示例：{json.dumps(rows[:2], ensure_ascii=False)}"
        return result.message
    if result.status == "awaiting_confirmation":
        return result.message
    if result.status == "blocked":
        return f"权限不足：{result.message}"
    return f"失败：{result.message}"


def get_provider() -> BaseProvider:
    """工厂函数：根据配置返回 mock 还是 DeepSeek。"""
    if settings.mock_mode:
        return MockProvider()
    return DeepSeekProvider()

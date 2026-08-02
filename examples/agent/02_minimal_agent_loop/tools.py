from typing import Any


class ToolExecutionError(Exception):
    """工具执行失败时主动抛出的错误。"""


# 工具 schema 可以理解成“给模型看的工具说明书”。
# Java 类比：它有点像接口文档，告诉调用方这个方法叫什么、需要哪些参数、返回什么能力。
# 注意：schema 只是帮助模型做决策；真正执行工具的仍然是后端 Python 函数。
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询教学版城市天气。适合回答天气、温度、是否下雨、出门建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，例如：北京、上海、深圳、广州、新加坡。",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_order_total",
            "description": "计算订单总价。适合回答单价、数量、优惠码相关问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_price": {"type": "number", "description": "单个商品价格，单位是元。"},
                    "quantity": {"type": "integer", "description": "购买数量，必须是正整数。"},
                    "discount_code": {
                        "type": "string",
                        "description": "优惠码，可选值：NONE、SAVE10、SAVE20。",
                    },
                },
                "required": ["item_price", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "检索教学版公司制度。适合回答报销、退款、假期、密码安全。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "检索关键词，例如：报销、退款、假期、密码。",
                    }
                },
                "required": ["keyword"],
            },
        },
    },
]


def list_tool_schemas() -> list[dict[str, Any]]:
    # 这个函数给 /tools 接口和 provider.py 的真实 DeepSeek 工具调用共用。
    # 这样接口里看到的工具清单，就是模型实际能选择的工具清单。
    return TOOL_SCHEMAS


def get_weather(city: str) -> dict[str, Any]:
    # 教学示例用固定假数据，避免学习者因为外部天气 API、网络、密钥问题跑不起来。
    weather_by_city = {
        "北京": {"temperature": 29, "condition": "晴", "advice": "适合出门，但注意防晒。"},
        "上海": {"temperature": 31, "condition": "多云", "advice": "体感偏热，建议带水。"},
        "深圳": {"temperature": 30, "condition": "阵雨", "advice": "建议带伞。"},
        "广州": {"temperature": 32, "condition": "雷阵雨", "advice": "晚高峰可能堵车，预留时间。"},
        "新加坡": {"temperature": 28, "condition": "小雨", "advice": "空气潮湿，建议带伞。"},
    }

    if city not in weather_by_city:
        # 这里主动抛出业务错误，而不是返回 None。
        # 这样 Agent Loop 可以把失败作为 observation 继续交给下一轮决策。
        raise ToolExecutionError(f"暂时没有城市 {city} 的教学版天气数据")

    weather = weather_by_city[city]
    return {
        "city": city,
        "temperature": weather["temperature"],
        "condition": weather["condition"],
        "advice": weather["advice"],
    }


def calculate_order_total(
    item_price: float,
    quantity: int,
    discount_code: str = "NONE",
) -> dict[str, Any]:
    # 工具内部仍然必须校验参数。
    # 原因是：参数可能来自模型，而模型输出不能被当成可信输入。
    if item_price <= 0:
        raise ToolExecutionError("item_price 必须大于 0")
    if quantity <= 0:
        raise ToolExecutionError("quantity 必须是正整数")

    discount_rate_by_code = {
        "NONE": 1.0,
        "SAVE10": 0.9,
        "SAVE20": 0.8,
    }
    normalized_code = discount_code.upper()
    if normalized_code not in discount_rate_by_code:
        raise ToolExecutionError(f"不支持的优惠码：{discount_code}")

    original_total = item_price * quantity
    final_total = original_total * discount_rate_by_code[normalized_code]
    return {
        "item_price": item_price,
        "quantity": quantity,
        "discount_code": normalized_code,
        "original_total": round(original_total, 2),
        "final_total": round(final_total, 2),
    }


def search_policy(keyword: str) -> dict[str, Any]:
    # 这里模拟一个很小的知识库。
    # 后续 RAG 智能体模块会把这个能力升级成真正的文档检索工具。
    policy_by_keyword = {
        "报销": "差旅报销需要在 7 天内提交发票、行程单和审批记录。",
        "退款": "退款申请需要订单号、付款截图和退款原因，财务会在 3 个工作日内处理。",
        "假期": "年假需要提前 2 个工作日提交申请，连续 5 天以上需要直属主管审批。",
        "密码": "密码必须至少 12 位，不能和历史 3 次密码重复。",
    }

    if keyword not in policy_by_keyword:
        raise ToolExecutionError(f"没有检索到关键词 {keyword} 对应的制度")

    return {
        "keyword": keyword,
        "content": policy_by_keyword[keyword],
    }


def run_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # run_tool 是唯一的工具执行入口。
    # Java 类比：可以把它看成 ToolService.dispatch(name, args)。
    # 这样 Agent Loop 不需要知道每个工具函数的细节，只需要传入工具名和参数。
    try:
        if tool_name == "get_weather":
            result = get_weather(city=str(arguments.get("city", "")))
        elif tool_name == "calculate_order_total":
            result = calculate_order_total(
                item_price=float(arguments.get("item_price", 0)),
                quantity=int(arguments.get("quantity", 0)),
                discount_code=str(arguments.get("discount_code", "NONE")),
            )
        elif tool_name == "search_policy":
            result = search_policy(keyword=str(arguments.get("keyword", "")))
        else:
            raise ToolExecutionError(f"工具 {tool_name} 不在白名单中")
    except (ValueError, TypeError) as exc:
        # ValueError / TypeError 常见于模型传错参数类型。
        # 例如 quantity 传成 "两个"，int("两个") 就会失败。
        return {
            "ok": False,
            "tool_name": tool_name,
            "arguments": arguments,
            "error": f"工具参数类型错误：{exc}",
        }
    except ToolExecutionError as exc:
        return {
            "ok": False,
            "tool_name": tool_name,
            "arguments": arguments,
            "error": str(exc),
        }

    return {
        "ok": True,
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
    }

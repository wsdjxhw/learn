from typing import Any


class ToolExecutionError(Exception):
    """工具执行失败时主动抛出的错误。"""


# 工具 schema 可以理解成“工具说明书”。
# Java 类比：它有点像给外部系统看的接口文档，告诉模型：
# 1. 工具叫什么名字；
# 2. 工具能解决什么问题；
# 3. 调用工具时必须传哪些参数；
# 4. 每个参数是什么类型。
#
# 注意：schema 不是 Python 自己运行工具所必须的。
# 它主要是给模型看的，帮助模型判断“我要不要调用这个工具，以及参数怎么填”。
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询一个城市的教学版天气信息。适合回答天气、温度、是否下雨这类问题。",
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
            "description": "计算订单总价。适合回答商品单价、数量、优惠码相关的问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_price": {
                        "type": "number",
                        "description": "单个商品价格，单位是元。",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "购买数量，必须是正整数。",
                    },
                    "discount_code": {
                        "type": "string",
                        "description": "优惠码。可选值：NONE、SAVE10、SAVE20。",
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
            "description": "检索教学版公司制度片段。适合回答报销、退款、假期、密码安全等规则问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "要检索的关键词，例如：报销、退款、假期、密码。",
                    }
                },
                "required": ["keyword"],
            },
        },
    },
]


def list_tool_schemas() -> list[dict[str, Any]]:
    # 返回工具 schema 列表，给 /tools 接口和真实模型调用共用。
    # 这里直接返回常量即可，因为教学示例里的工具列表是固定的。
    return TOOL_SCHEMAS


def get_weather(city: str) -> dict[str, Any]:
    # 这个工具不调用真实天气 API。
    # 教学阶段先用稳定的假数据，让学习重点放在“工具调用链路”上。
    weather_by_city = {
        "北京": {"temperature": 29, "condition": "晴", "advice": "适合出门，但注意防晒。"},
        "上海": {"temperature": 31, "condition": "多云", "advice": "体感偏热，建议带水。"},
        "深圳": {"temperature": 30, "condition": "阵雨", "advice": "建议带伞。"},
        "广州": {"temperature": 32, "condition": "雷阵雨", "advice": "晚高峰可能堵车，预留时间。"},
        "新加坡": {"temperature": 28, "condition": "小雨", "advice": "空气潮湿，建议带伞。"},
    }

    if city not in weather_by_city:
        # 主动抛错可以让调用方区分“工具没有查到”和“程序崩溃”。
        raise ToolExecutionError(f"暂时没有城市 {city} 的教学版天气数据")

    result = weather_by_city[city]
    return {
        "city": city,
        "temperature": result["temperature"],
        "condition": result["condition"],
        "advice": result["advice"],
    }


def calculate_order_total(
    item_price: float,
    quantity: int,
    discount_code: str = "NONE",
) -> dict[str, Any]:
    # 后端不能完全相信模型传来的参数。
    # 模型可能把数量传成 0、负数，或者传入不存在的优惠码。
    # 所以工具内部仍然要做校验，这和普通 API 的参数校验是同一个道理。
    if item_price <= 0:
        raise ToolExecutionError("item_price 必须大于 0")

    if quantity <= 0:
        raise ToolExecutionError("quantity 必须是正整数")

    discount_rate_by_code = {
        "NONE": 0.0,
        "SAVE10": 0.10,
        "SAVE20": 0.20,
    }

    normalized_code = discount_code.upper()
    if normalized_code not in discount_rate_by_code:
        raise ToolExecutionError("discount_code 只能是 NONE、SAVE10 或 SAVE20")

    original_total = item_price * quantity
    discount_rate = discount_rate_by_code[normalized_code]
    discount_amount = original_total * discount_rate
    final_total = original_total - discount_amount

    return {
        "item_price": item_price,
        "quantity": quantity,
        "discount_code": normalized_code,
        "original_total": round(original_total, 2),
        "discount_amount": round(discount_amount, 2),
        "final_total": round(final_total, 2),
    }


def search_policy(keyword: str) -> dict[str, Any]:
    # 这个工具模拟“检索资料库”。
    # 后续 RAG Agent 模块会把这里替换成真正的文档检索工具。
    policy_by_keyword = {
        "报销": "差旅报销需要在行程结束后 7 天内提交发票和审批单。",
        "退款": "订单支付后 24 小时内可以原路退款，超过 24 小时需要人工审核。",
        "假期": "年假需要至少提前 3 个工作日申请，病假需要补充证明材料。",
        "密码": "内部系统密码至少 12 位，并且不能和最近 3 次密码重复。",
        "加班": "加班需要提前申请，并且每月加班总时长不能超过 36 小时。",
    }

    matched_items = []
    for policy_keyword, content in policy_by_keyword.items():
        # 这里用最简单的包含匹配，方便初学者先看懂流程。
        # 更复杂的语义检索会放到后续 RAG 工具 Agent 模块。
        if keyword in policy_keyword or policy_keyword in keyword:
            matched_items.append(
                {
                    "keyword": policy_keyword,
                    "content": content,
                    "source": f"mock_policy:{policy_keyword}",
                }
            )

    if not matched_items:
        raise ToolExecutionError(f"没有检索到和 {keyword} 相关的制度片段")

    return {
        "query": keyword,
        "matches": matched_items,
    }


def run_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # run_tool 是工具执行入口。
    # Java 类比：可以把它理解成一个很小的 Dispatcher，根据 name 分发到不同 Service 方法。
    #
    # 参数 arguments 来自模型决策或 /tool/run 请求体。
    # 这里不用 if tool_name in globals() 这类动态写法，是为了避免模型调用未授权函数。
    # 真实项目里，工具白名单非常重要。
    try:
        if tool_name == "get_weather":
            return {
                "ok": True,
                "tool_name": tool_name,
                "result": get_weather(city=str(arguments.get("city", ""))),
            }

        if tool_name == "calculate_order_total":
            return {
                "ok": True,
                "tool_name": tool_name,
                "result": calculate_order_total(
                    item_price=float(arguments.get("item_price", 0)),
                    quantity=int(arguments.get("quantity", 0)),
                    discount_code=str(arguments.get("discount_code", "NONE")),
                ),
            }

        if tool_name == "search_policy":
            return {
                "ok": True,
                "tool_name": tool_name,
                "result": search_policy(keyword=str(arguments.get("keyword", ""))),
            }

        return {
            "ok": False,
            "tool_name": tool_name,
            "error": f"未知工具：{tool_name}",
        }

    except (ValueError, TypeError) as exc:
        # ValueError / TypeError 通常说明参数类型转换失败。
        # 例如模型传入了 quantity="abc"，int("abc") 就会失败。
        return {
            "ok": False,
            "tool_name": tool_name,
            "error": f"工具参数格式错误：{exc}",
        }
    except ToolExecutionError as exc:
        return {
            "ok": False,
            "tool_name": tool_name,
            "error": str(exc),
        }

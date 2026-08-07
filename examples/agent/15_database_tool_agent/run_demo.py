"""
run_demo.py —— 命令行演示脚本（不用起 FastAPI 也能跑通全链路）

用法：
  python run_demo.py                 # 按预设场景演示一遍
  python run_demo.py --interactive   # 进入问答模式，自己输入问题

默认走 mock 模式（无 API Key 也能跑）。想用真实模型，把 .env 里的
MOCK_MODE 改成 false 并填好 DEEPSEEK_API_KEY。

它会演示完整链路：
  查询 -> 直接返回数据
  写操作 -> 先生成确认单 -> 批准 -> 真正执行 -> 审计
"""

import sys

# Windows 控制台默认可能是 GBK 编码，强制用 UTF-8 输出，避免中文乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agent import run_agent
from database import init_db
from provider import get_provider
from seed import seed_if_empty
from settings import settings
from tool_registry import approve_confirmation
from security import UserContext, role_for_key


def print_steps(steps):
    """把 Agent 的中间步骤打印成缩进列表，方便看清它干了什么。"""
    for s in steps:
        if s.step == "tool_call":
            print(f"    [工具调用] {s.tool_name}  args={s.args}")
        else:
            print(f"    [观察结果] {s.content}")


def demo_one(provider, question, api_key):
    """跑一次对话并打印结果。返回响应对象。"""
    role = role_for_key(api_key)
    user = UserContext(api_key=api_key, role=role)
    resp = run_agent(question, user, provider)
    print(f"\nQ: {question}   （角色: {role}）")
    print_steps(resp.steps)
    print(f"A: {resp.answer}")
    return resp


def main():
    init_db()
    seed_if_empty()
    provider = get_provider()

    print("=" * 60)
    print(f"数据库工具智能体 —— demo")
    print(f"模型模式：{'mock（无需 API Key）' if settings.mock_mode else 'DeepSeek（真实模型）'}")
    print("=" * 60)

    viewer_key = settings.viewer_api_key
    operator_key = settings.operator_api_key

    # ---------- 1. 只读查询：直接执行 ----------
    demo_one(provider, "统计各状态的订单数量", viewer_key)
    demo_one(provider, "查询北京的客户", viewer_key)
    demo_one(provider, "查询所有订单", viewer_key)

    # ---------- 2. 写操作：先生成确认单，批准后才真正执行 ----------
    # 订单2 当前是已付款(paid)，可以发货(shipped)，走"申请 -> 批准 -> 生效"完整流程
    resp = demo_one(provider, "给订单2发货", operator_key)
    if resp.confirmation_id:
        conf_id = resp.confirmation_id
        print(f"\n>>> 模拟审批：批准确认单 #{conf_id} ...")
        result, req = approve_confirmation(conf_id, role_for_key(operator_key), operator_key)
        print(f">>> 审批结果：{result.status} | {result.message}")
    else:
        print("\n>>> 本次没有生成确认单（可能被拦或直接失败）")

    demo_one(provider, "创建一个订单，客户2，买一台显示器，金额1299元", operator_key)

    # ---------- 3. 业务规则：违反业务规则的写请求，审批时会被拒绝 ----------
    # 订单3 已是已发货(shipped)，属于"履约中订单"，按规则不能删除，批准时会被业务规则拦住
    resp = demo_one(provider, "删除订单3", operator_key)
    if resp.confirmation_id:
        print(f"\n>>> 模拟审批：批准确认单 #{resp.confirmation_id} ...（预计被业务规则拒绝）")
        result, _req = approve_confirmation(resp.confirmation_id, role_for_key(operator_key), operator_key)
        print(f">>> 审批结果：{result.status} | {result.message}")

    # ---------- 4. 权限对比：viewer 尝试写操作会被拦 ----------
    demo_one(provider, "删除订单8", viewer_key)

    print("\n" + "=" * 60)
    print("提示：查看所有操作记录请启动接口后访问 GET /audit-logs")
    print("=" * 60)


if __name__ == "__main__":
    if "--interactive" in sys.argv:
        init_db()
        seed_if_empty()
        provider = get_provider()
        print("交互模式（输入问题，Ctrl+C 退出）")
        while True:
            try:
                q = input(">>> ")
            except (EOFError, KeyboardInterrupt):
                break
            if not q.strip():
                continue
            demo_one(provider, q.strip(), settings.operator_api_key)
    else:
        main()

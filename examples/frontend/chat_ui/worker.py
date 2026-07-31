import time

from database import (
    create_message,
    list_recent_messages,
    mark_task_failed,
    mark_task_running,
    mark_task_succeeded,
)
from provider import generate_reply
from retriever import search_sources


def process_chat_task(task_id: int, session_id: int, user_message: str) -> None:
    # 这个函数是后台任务处理器，类比 Java 里的 Job Handler。
    # 它不直接给浏览器返回内容；浏览器需要通过 GET /api/tasks/{task_id} 轮询状态。
    try:
        mark_task_running(task_id)

        # 故意保留短暂等待，让前端能观察 running 状态。
        # 真实项目里这里可能是调用模型、检索 RAG、生成长报告。
        time.sleep(1.2)

        if "FAIL_TASK" in user_message:
            raise ValueError("Input text requested a simulated failure")

        # 这里才是真正的“短期记忆”：
        # 不是只把历史消息展示在页面上，而是在生成下一条 assistant 回复前，
        # 从 messages 表读取当前会话最近几条消息，交给 provider 作为上下文。
        history = list_recent_messages(session_id=session_id, limit=8)
        sources = search_sources(user_message)
        reply = generate_reply(
            user_message=user_message,
            sources=sources,
            history=history,
        )
        assistant_message = create_message(
            session_id=session_id,
            role="assistant",
            content=reply,
        )
        mark_task_succeeded(
            task_id=task_id,
            result_message_id=assistant_message["id"],
            sources=sources,
        )
    except Exception as exc:
        # 后台任务失败不能静默消失，要把错误保存下来给前端展示。
        mark_task_failed(task_id=task_id, error_message=str(exc))

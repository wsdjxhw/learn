import json


def format_sse(event: str, data: dict) -> str:
    # SSE 是一段特殊格式的文本，不是普通 JSON。
    # 每条事件至少包含 event 和 data 两行，最后必须用空行结束。
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def status_event(task: dict) -> str:
    # status 事件告诉前端任务当前状态。
    return format_sse(
        "status",
        {
            "task_id": task["id"],
            "status": task["status"],
            "error_message": task["error_message"],
        },
    )


def sources_event(task: dict) -> str:
    # sources 单独作为事件发送，前端收到后只需要刷新右侧 sources 面板。
    return format_sse("sources", {"items": task["sources"]})


def done_event(task: dict) -> str:
    # done 表示这条 SSE 连接可以关闭。
    return format_sse(
        "done",
        {
            "task_id": task["id"],
            "status": task["status"],
            "ok": task["status"] == "succeeded",
        },
    )


def task_error_event(task: dict) -> str:
    # 避免命名为 error，因为浏览器 EventSource 自己也有 error 事件。
    # task_error 表示后端任务失败，不等于网络连接失败。
    return format_sse(
        "task_error",
        {
            "task_id": task["id"],
            "message": task["error_message"] or "Task failed",
        },
    )

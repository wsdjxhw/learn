import time

from db import mark_task_failed, mark_task_running, mark_task_succeeded
from provider import summarize_text


def process_summary_task(task_id: int, input_text: str) -> None:
    # 这个函数就是后台任务处理器。
    # 类比 Java 里的 Job Handler 或消息队列 Consumer。
    #
    # 它不会直接返回给浏览器。
    # 浏览器拿到 task_id 后，要通过 GET /summary-tasks/{task_id} 查询结果。
    try:
        mark_task_running(task_id)

        # 模拟耗时处理，让你在 /docs 里更容易观察 pending/running/succeeded。
        # 真实项目里，这里可能是解析 PDF、调用模型、生成报告。
        time.sleep(2)

        if "FAIL_TASK" in input_text:
            # 这是故意保留的失败入口，用来练习 failed 状态。
            # 提交包含 FAIL_TASK 的文本，就能观察错误如何保存。
            raise ValueError("Input text requested a simulated failure")

        result = summarize_text(input_text)
        mark_task_succeeded(task_id, result)
    except Exception as exc:
        # 后台任务不能让异常直接消失，必须把失败原因落库。
        mark_task_failed(task_id, str(exc))

import re

KNOWLEDGE_BASE = [
    {
        "title": "聊天历史",
        "content": "聊天 UI 需要会话列表和消息历史。后端通常保存 sessions 和 messages 两类数据。",
    },
    {
        "title": "后台任务",
        "content": "耗时 AI 任务适合先返回 task_id，再通过轮询查询 pending、running、succeeded、failed 状态。",
    },
    {
        "title": "RAG sources",
        "content": "RAG 问答需要把 sources 返回给前端，让用户知道答案参考了哪些资料片段。",
    },
    {
        "title": "认证和限流",
        "content": "真实 AI API 通常需要 API Key 鉴权、限流、请求日志、错误日志和成本记录。",
    },
    {
        "title": "流式输出",
        "content": "流式输出可以让前端边接收边显示内容，常见协议包括 Server-Sent Events。",
    },
]


def tokenize(text: str) -> list[str]:
    # 这里使用简单关键词检索，只为前端 sources 展示提供稳定样例。
    # 真正的 RAG 检索已经在前面的模块里单独学习过。
    return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text.lower())


def search_sources(question: str, top_k: int = 3) -> list[dict]:
    tokens = tokenize(question)
    scored_sources: list[dict] = []

    for item in KNOWLEDGE_BASE:
        content = f"{item['title']} {item['content']}".lower()
        score = 0
        for token in tokens:
            if token and token in content:
                score += 1

        if score > 0:
            scored_sources.append(
                {
                    "title": item["title"],
                    "snippet": item["content"],
                    "score": float(score),
                }
            )

    if not scored_sources:
        return [
            {
                "title": "默认学习资料",
                "snippet": "没有命中特定资料时，前端仍然要能展示空 sources 或默认说明。",
                "score": 0.1,
            }
        ]

    scored_sources.sort(key=lambda source: source["score"], reverse=True)
    return scored_sources[:top_k]

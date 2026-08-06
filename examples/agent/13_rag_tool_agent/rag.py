from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Chunk, Document
from retriever import retrieve_relevant_chunks
from text_splitter import split_text


def create_document(
    db: Session,
    title: str,
    content: str,
    chunk_size: int = 300,
    overlap: int = 50,
) -> dict[str, Any]:
    # 知识库录入：把一整篇文档切分成 chunks，然后一起入库。
    # db 是 FastAPI 通过 Depends(get_db) 注入的数据库会话，类比 Java 的 EntityManager。
    chunks = split_text(text=content, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        raise ValueError("文档内容为空，无法入库。")

    document = Document(title=title)
    db.add(document)
    # flush() 会把 document 的 INSERT 立即发给数据库，让 document.id 生成出来。
    # 不 commit 是为了后面如果失败可以一起回滚。初学者可以先理解成“先拿到 id”。
    db.flush()

    for index, chunk_text in enumerate(chunks):
        db.add(Chunk(document_id=document.id, chunk_index=index, content=chunk_text))

    db.commit()
    db.refresh(document)
    return {
        "document_id": document.id,
        "title": document.title,
        "chunk_count": len(chunks),
    }


def list_documents(db: Session) -> list[dict[str, Any]]:
    # 查看知识库里有哪些文档，并带上每个文档的 chunk 数量。
    rows = db.execute(
        select(Document.id, Document.title, Document.created_at, Chunk.id.label("chunk_id"))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .order_by(Document.id.desc())
    ).all()

    # 因为 outerjoin 会让每个 chunk 各占一行，这里按 document 聚合统计数量。
    by_document: dict[int, dict[str, Any]] = {}
    for document_id, title, created_at, chunk_id in rows:
        item = by_document.setdefault(
            document_id,
            {"document_id": document_id, "title": title, "created_at": created_at.isoformat(), "chunk_count": 0},
        )
        if chunk_id is not None:
            item["chunk_count"] += 1
    return list(by_document.values())


def list_chunks(db: Session, document_id: int) -> list[dict[str, Any]]:
    # 查看某篇文档被切成了哪些片段，学习时用来确认切分结果。
    rows = db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index.asc())
    ).scalars().all()
    return [
        {"id": row.id, "document_id": row.document_id, "chunk_index": row.chunk_index, "content": row.content}
        for row in rows
    ]


def list_all_chunks(db: Session) -> list[dict[str, Any]]:
    # 检索阶段会扫描所有 chunks。
    # 这里用 JOIN 把每段文本的“所属文档标题”也带出来，这样 sources 里能告诉用户来自哪篇文档。
    # 真实项目里这里会换成向量数据库的 ANN 检索，而不是全表扫描。
    rows = db.execute(
        select(Chunk, Document.title)
        .join(Document, Document.id == Chunk.document_id)
        .order_by(Chunk.id.asc())
    ).all()
    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "document_title": title,
        }
        for chunk, title in rows
    ]


def search_documents_in_db(
    db: Session,
    query: str,
    top_k: int = 3,
) -> dict[str, Any]:
    # 这是被 tools.py 调用的检索核心：
    # 1. 取出知识库全部 chunks；
    # 2. 用关键词相关度找到最相关的 top_k 个；
    # 3. 返回结构化结果，同时带上 count，方便 Agent 判断“有没有查到资料”。
    all_chunks = list_all_chunks(db)
    if not all_chunks:
        return {
            "ok": True,
            "tool_name": "search_documents",
            "count": 0,
            "results": [],
            "note": "知识库为空，请先通过 /documents 或 /demo/seed 录入文档。",
        }

    results = retrieve_relevant_chunks(question=query, chunks=all_chunks, top_k=top_k)
    if not results:
        return {
            "ok": True,
            "tool_name": "search_documents",
            "count": 0,
            "results": [],
            "note": "知识库中没有任何片段与本次查询相关。",
        }

    return {
        "ok": True,
        "tool_name": "search_documents",
        "count": len(results),
        "results": results,
        "note": f"检索到 {len(results)} 条相关资料。",
    }


def seed_demo_documents(db: Session) -> list[dict[str, Any]]:
    # 教学便利接口：一键写入几篇示例文档，让你不用自己敲长文本也能立刻测试 RAG Agent。
    # 真实项目不会有这种“塞假数据”的接口，而是通过文档上传流程写入知识库。
    samples: list[dict[str, str]] = [
        {
            "title": "公司报销制度",
            "content": (
                "一、报销基本流程：员工发生费用后，先填写报销申请单，注明费用类型、金额、发生日期和事由，"
                "并附上发票照片或电子发票。部门负责人审批通过后，提交给财务部门复核。财务复核无误后，"
                "在十个工作日内完成打款。\n"
                "二、报销金额上限：交通费单次不超过五百元，餐饮费每人每天不超过一百元，住宿费按城市标准执行。"
                "超出上限的部分需要提前申请特殊审批。\n"
                "三、注意事项：发票抬头必须为公司全称，个人抬头的发票不予报销。报销单提交后一般不支持撤回，"
                "如需修改请直接联系财务人员。"
            ),
        },
        {
            "title": "员工请假制度",
            "content": (
                "一、请假类型：包括年假、病假、事假、婚假、产假和调休。年假按入职年限计算，入职满一年有五天，"
                "满三年有十天。病假需要提供医院开具的病假证明，否则按事假处理。\n"
                "二、请假流程：提前在办公系统提交请假申请，说明请假起止时间和原因。三天以内由直属主管审批，"
                "三天以上需要部门负责人审批，连续五天以上需要提交 HR 备案。\n"
                "三、调休规则：加班满四小时可折算半天调休，加班满八小时可折算一天调休。调休有效期三个月，"
                "过期自动作废。"
            ),
        },
        {
            "title": "办公行为规范手册",
            "content": (
                "一、考勤要求：工作日上下班需打卡，迟到超过三十分钟按事假半天处理。加班需要提前报备，"
                "未报备的加班不计入调休时长。\n"
                "二、信息安全：公司内部资料不得通过个人网盘或聊天工具外传。涉及客户数据的文件必须加密保存，"
                "离职时统一交回全部涉密材料。\n"
                "三、行为准则：与客户沟通时应使用正式称谓和邮件签名，不得私自承诺折扣或服务范围。"
                "发现违反规定的行为应及时向合规部门举报。"
            ),
        },
    ]

    created: list[dict[str, Any]] = []
    for sample in samples:
        created.append(
            create_document(
                db=db,
                title=sample["title"],
                content=sample["content"],
                chunk_size=150,
                overlap=40,
            )
        )
    return created

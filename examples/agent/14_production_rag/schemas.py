"""
schemas.py - Pydantic DTO（数据传输对象）

职责：定义接口的“请求体长什么样、响应体长什么样”。
     这些模型只在网络层使用，和数据库的 ORM 模型（models.py）是两套东西。

为什么要单独定义 DTO，而不是直接返回 ORM 对象？
1. 安全：ORM 对象里可能有不该返回的字段（比如这里的内部关系），DTO 只暴露想给前端的字段。
2. 稳定：前端依赖的是 DTO 契约，数据库表结构怎么改都不影响接口返回格式。
3. 校验：Pydantic 会在入口自动校验请求体，字段缺失/类型错误直接返回 422。

类比 Java：Request DTO / Response DTO，对应 controller 的入参和出参。
"""
from typing import Optional

from pydantic import BaseModel, Field


# ------------------------- 请求 DTO（客户端 -> 后端） -------------------------

class DocumentUploadResult(BaseModel):
    """文档上传 + 解析 + 入库 的结果响应。"""
    document_id: int
    title: str
    filename: str
    content_type: str
    file_size: int
    chunk_count: int
    owner_id: str
    visibility: str
    category: Optional[str] = None
    tags: Optional[str] = None


# ------------------------- 文档管理 DTO -------------------------

class ChunkItem(BaseModel):
    """文档详情里的单个片段。"""
    index: int
    content: str
    char_count: int


class DocumentListItem(BaseModel):
    """文档列表里的一行（不携带 chunks，列表页不需要全量片段）。"""
    id: int
    title: str
    filename: str
    content_type: str
    file_size: int
    owner_id: str
    visibility: str
    category: Optional[str] = None
    tags: Optional[str] = None
    chunk_count: int
    created_at: str = Field(..., description="入库时间（已转成字符串便于展示）")


class DocumentDetail(DocumentListItem):
    """文档详情（列表项 + 原文预览 + 全部片段）。"""
    content_preview: str
    chunks: list[ChunkItem] = []


# ------------------------- 工具执行 DTO -------------------------

class ToolRunRequest(BaseModel):
    """手动执行工具时的请求体。"""
    tool_name: str = Field(..., description="工具名，本模块只有 search_documents")
    arguments: dict = Field(default_factory=dict, description="工具参数，例如 {'query': '报销流程'}")


class SearchRequest(BaseModel):
    """手动检索的请求体。

    注意：真正的 RAG 检索不是“给一句问题就返回”，而是三个可控参数：
    - query：用户的检索词/问题；
    - metadata_filters：按文档元数据过滤（真实项目里这个最常用）；
    - top_k / top_n：召回多少、最终留多少（控制成本和上下文长度）。
    """
    query: str = Field(..., min_length=1, description="检索词或用户问题")
    category: Optional[str] = Field(None, description="只检索这个分类的文档，不传=不过滤")
    tags: Optional[str] = Field(None, description="只检索包含这些标签（逗号分隔）的文档")
    top_k: int = Field(20, ge=1, le=100, description="召回候选数（粗排阶段保留多少）")
    top_n: int = Field(3, ge=1, le=10, description="最终精排后保留的片段数")


class SearchChunkResult(BaseModel):
    """检索结果里的单个片段（供前端展示候选和最终结果）。"""
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    score: float = Field(..., description="该片段在这一步的打分")


class SearchResponse(BaseModel):
    """手动检索的响应。

    故意同时返回 raw_candidates 和 reranked_results：
    这是本模块的“对比教学点”——让学习者亲眼看到
    “检索 top_k 的顺序”和“rerank 后的顺序”为什么不一样。
    """
    query: str
    user_id: str
    # 检索阶段（粗排）返回的候选，按粗分排序
    raw_candidates: list[SearchChunkResult]
    # rerank 阶段（精排）之后的最终结果，按精分排序
    reranked_results: list[SearchChunkResult]
    filtered_documents: int = Field(..., description="按权限+metadata 过滤后可见的文档数")


# ------------------------- Agent 对话相关 DTO -------------------------

class AgentChatRequest(BaseModel):
    """/agent/chat 的请求体。"""
    message: str = Field(..., min_length=1, description="用户消息")


class AgentSource(BaseModel):
    """回答的引用来源（sources 里的一项）。"""
    document_id: int
    document_title: str
    content: str
    score: float


class AgentChatResponse(BaseModel):
    """/agent/chat 的响应。

    保持和模块 13 一致的结构：used_tool + answer + sources。
    前端渲染时：answer 显示正文，sources 显示“回答依据”。
    """
    used_tool: bool
    tool_name: Optional[str] = None
    answer: str
    sources: list[AgentSource] = []


# ------------------------- 评测前置 DTO -------------------------

class EvalCaseResult(BaseModel):
    """单个评测 case 的结果。"""
    case_id: int
    query: str
    expected_documents: list[str]
    # 期望文档标题是否出现在最终 top_n 里（recall@n 的单个样本）
    hit: bool
    # 实际命中的期望文档（有几个对几个）
    matched: list[str]
    # 本次检索的最终 top_n 文档标题，方便人工核对
    returned_documents: list[str]


class EvalRunResponse(BaseModel):
    """一次评测运行的汇总结果。

    真实项目里评测报告要能回答：
    “我改了切分策略 / 加了 rerank，检索质量到底变好了没有？”
    这里给出最朴素的指标：期望文档出现在最终结果里的比例（recall@n）。
    """
    total_cases: int
    passed: int
    recall_at_n: float = Field(..., description="召回率 = 通过数 / 总数")
    results: list[EvalCaseResult]

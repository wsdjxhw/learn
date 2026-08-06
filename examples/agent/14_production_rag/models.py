"""
models.py - ORM 模型（数据库表结构）

职责：用 Python 类描述数据库表。SQLAlchemy 会把类 -> 表、属性 -> 列一一对应。

这里有两张表：
1. documents 表：一份上传文档的“档案信息”（标题、归属用户、可见范围、分类、标签）。
   类比 Java：这是 Entity 层，描述“一份文档这一行记录”。
2. chunks 表：一份文档切分后的多个文本片段。
   RAG 检索真正匹配的是 chunk，而不是整篇文档。

为什么要拆成两张表？
真实项目里一份文档会被切成几十上百个 chunk。
如果都塞在同一张表，文档元信息会重复存储几百次，权限过滤和删除都会变麻烦。
拆表后：删除文档 = 删 documents 行 + 级联删它的所有 chunks。
用 relationship + cascade 声明这个“一对多、删除级联”关系。

和 schemas.py 的 Pydantic 模型有什么区别？
- models.py：ORM 模型，对应数据库一行。它“连接着数据库”，有 id、外键等。
- schemas.py：DTO（数据传输对象），只在接口请求/响应时用，不直接碰数据库。
这就是 FastAPI 项目里“ORM 和 DTO 分离”的原因：数据库结构和对外契约可以独立变化。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from database import Base


class Document(Base):
    """文档表：一份上传文件对应的元信息行。"""
    __tablename__ = "documents"

    # primary_key=True 自增主键，数据库自动生成，类比 Java 的 @Id + @GeneratedValue
    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(200), nullable=False)  # 文档标题（上传时可指定，默认用文件名）
    filename = Column(String(255), nullable=False)  # 原始文件名，用于展示和排查
    content_type = Column(String(50), nullable=False)  # 解析后的文本类型：text/markdown/pdf
    file_size = Column(Integer, default=0)  # 原始文件字节数，用于统计
    content_preview = Column(Text, default="")  # 原文开头一段预览，方便列表页不读全 chunk

    # ---------- 文档级权限隔离相关字段（本模块核心） ----------
    # owner_id：文档归属用户。真实项目里是多租户隔离的租户 ID 或组织 ID。
    # 教学版简化为用户标识字符串（alice / bob / admin）。
    owner_id = Column(String(50), nullable=False, index=True)
    # visibility：可见范围。public=所有人可见；private=仅 owner 和 admin 可见。
    # 真实项目通常不只有两级，而是用权限表 / 部门树 / 共享成员列表，教学版先讲清楚两级够用。
    visibility = Column(String(20), nullable=False, default="private")

    # ---------- metadata（元数据）相关字段 ----------
    # 真实项目里 metadata 一般是一个 JSON 字段（PostgreSQL 的 JSONB），
    # 可以存任意键值。教学版为了直观，先拆成两个常见字段演示“metadata 过滤”。
    category = Column(String(100), nullable=True, index=True)  # 分类，如 人事 / 财务 / 产品
    tags = Column(String(200), nullable=True)  # 逗号分隔标签，如 "报销,流程"

    # 辅助统计和时间
    chunk_count = Column(Integer, default=0)  # 这份文档被切成了多少段
    created_at = Column(DateTime, server_default=func.now())  # 入库时间，由数据库生成

    # relationship：声明 documents 和 chunks 的一对多关系。
    # cascade="all, delete-orphan"：删除文档时，SQLAlchemy 自动级联删除它的所有 chunk。
    # 类比 Java：@OneToMany(mappedBy=..., cascade=CascadeType.ALL, orphanRemoval=true)
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """chunk 表：文档切分后的一个文本片段，是检索的最小单位。"""
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    # 外键：这个 chunk 属于哪份文档。
    # ForeignKey("documents.id") 里的字符串格式是“表名.列名”。
    # 类比 Java：@ManyToOne + @JoinColumn(name="document_id")
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    index = Column(Integer, nullable=False)  # 第几个片段（从 0 开始），用于还原原文顺序
    content = Column(Text, nullable=False)  # 片段正文
    char_count = Column(Integer, default=0)  # 片段字数，用于展示和打分

    # 反向关系：通过 chunk.document 能拿到所属文档（连带它的 title/category/owner 等）。
    # 检索时经常需要“这个 chunk 来自哪篇文档、文档谁可见”，靠这个关系一次取到。
    document = relationship("Document", back_populates="chunks")

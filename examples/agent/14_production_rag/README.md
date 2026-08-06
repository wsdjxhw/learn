# 14 生产级 RAG 工程

本模块解决的问题：模块 13 的 RAG 是“demo 级”——文档靠手写 seed 导入、所有文档对所有人可见、检索只有 bigram 关键词、没有排序优化。真实 RAG 项目里，**“能检索”和“能上线”是两回事**。本模块把 RAG 升级成真实项目需要的工程能力：**真实文件上传解析、metadata 过滤、文档级权限隔离、检索后 rerank、评测前置数据**。

本模块是独立可运行模块。它复用了前面积累的能力（RAG 检索、Agent 决策、SQLAlchemy、FastAPI），但代码独立成目录，不跨目录 import。

## 学习目标

学完本模块，你应该能讲清楚：

- RAG 在真实项目里是怎么处理文档的：**文件上传 → 解析 → 切分 → 入库**，而不是手写字符串。
- **metadata 过滤**和关键词检索的区别：一个是硬条件（分类不对根本不出现），一个是软条件（相关度打分）。
- **文档级权限隔离**为什么必须在 SQL 层做，以及它和“工具权限”是两类不同的权限。
- 为什么检索 top-k 之后还要 **rerank**，粗排和精排各负责什么。
- 为什么“检索到内容 ≠ 检索到正确答案”，**相关性阈值**是怎么防止模型编答案的。
- 为什么改完检索/切分/rerank 之后必须用**固定数据集**证明变好（评测前置）。

你应该能做：

- 用 `/demo/seed-docs` 一键导入示例文档，也能用 `/documents/upload` 上传自己的真实 txt/md/pdf 文件。
- 用不同 API Key 验证“不同用户看到不同文档”，看懂数据级权限的效果。
- 用 `/search` 对比粗排和精排，说出为什么顺序会变。
- 用 `/eval/run` 跑评测，解释 alice 和 bob 的 recall 为什么不同。

## 和前后模块的关系

本模块继承（复用能力，不复制代码）：

- 模块 04 / 13 的 RAG 检索能力：切分、bigram 匹配、sources 引用。
- 模块 13 的 Agent 模式：`search_documents` 工具、Agent 决策“要不要检索”、检索不到诚实说不足。
- 模块 10-12 的 API Key 身份和工具白名单思想（本模块简化为只保留一个工具）。
- 更早的 SQLAlchemy / FastAPI / DeepSeek 调用地基。

本模块新增（前面没有的核心能力）：

- **文件上传与解析**：`UploadFile` + 按扩展名选解析器（txt/md/pdf），错误处理、大小限制。
- **metadata 过滤**：文档带分类和标签，检索时按 metadata 硬过滤。
- **文档级权限隔离**：文档有 `owner_id` 和 `visibility`，检索/查看/删除都按用户身份过滤。
- **两阶段检索**：粗排（bigram 召回 top-k）→ 精排（rerank 取 top-n），并对比展示。
- **相关性阈值**：低分“巧合命中”的片段不进回答，防止基于无关材料编答案。
- **评测前置数据**：`eval_cases.json` + `/eval/run`，输出 recall@n。

本模块为后面准备：

- 模块 15（数据库工具智能体）：同样的“工具 + 权限 + 记录”模式会用到结构化数据上。
- 模块 21（Agent 评测）：会复用并扩展 `eval_cases.json` 的数据格式和运行入口。
- 完整项目一（企业知识库 Agent）：文档上传、权限隔离、sources 引用都会直接复用本模块的设计。

## 启动方式

```bash
cd examples/agent/14_production_rag
pip install -r requirements.txt
uvicorn main:app --reload --port 8015
```

打开：

```text
http://127.0.0.1:8015/docs
```

默认 mock 模式，不需要真实模型 API Key。

## 教学 API Key 与文档权限

```text
learner-key   -> alice（viewer）
operator-key  -> bob（operator）
admin-key     -> admin（admin）
```

请求头：`X-API-Key`。不传时默认是 `learner-key`（alice）。

每个 API Key 对应一个“用户身份”，文档权限规则（`permissions.py`）：

| 用户 | 能看的文档 | 能删的文档 |
|------|-----------|-----------|
| admin | 所有文档 | 所有文档 |
| 普通用户 | public 文档 + 自己拥有的 private 文档 | 只有自己的文档 |

示例文档里的《产品路线图（内部机密）》是 private，seed 时归 alice 所有。所以 alice 能看到 4 篇，bob 只能看到 3 篇。

## 接口测试顺序（按这个顺序学，不要乱点）

### 1. 确认服务启动

```bash
curl http://127.0.0.1:8015/health
```

要看到 `module = 14_production_rag, model_mode = mock`。

### 2. 一键导入示例文档

```bash
curl -X POST http://127.0.0.1:8015/demo/seed-docs
```

要看到 `created` 里有 4 篇文档（报销流程、请假制度、规章制度大全、产品路线图），重复调用会进 `skipped`（幂等）。

### 3. 体验文档级权限隔离

```bash
# alice：能看到 4 篇
curl http://127.0.0.1:8015/documents

# bob：只能看到 3 篇（看不到 alice 的私有文档）
curl -H "X-API-Key: operator-key" http://127.0.0.1:8015/documents
```

### 4. 对比粗排和精排（本模块核心）

```bash
curl -X POST http://127.0.0.1:8015/search \
  -H "Content-Type: application/json" \
  -d '{"query": "报销流程怎么走", "top_k": 20}'
```

看两件事：

- `raw_candidates` 第一条是文档标题段（#0），因为标题里“报销流程”几个字全都命中；
- `reranked_results` 第一条变成“报销审批流程”那段（#4），因为那段内容才是用户真正要的。
  粗排按“共现字多不多”，精排按“覆盖率 + 位置 + 标题 + 长度”，这就是为什么顺序会变。

### 5. 观察 metadata 过滤

```bash
curl -X POST http://127.0.0.1:8015/search \
  -H "Content-Type: application/json" \
  -d '{"query": "报销", "category": "财务"}'
```

`filtered_documents` 会变成 1（只有财务分类的报销文档参与检索），且结果不再混入《公司规章制度大全》。

### 6. 验证权限在检索中的效果

```bash
# bob 检索产品路线图：返回空，因为他看不到 alice 的私有文档
curl -X POST http://127.0.0.1:8015/search \
  -H "X-API-Key: operator-key" -H "Content-Type: application/json" \
  -d '{"query": "产品路线图三季度上线什么功能"}'
```

### 7. Agent 对话

```bash
# alice 问报销问题：used_tool=true，sources 有 3 条
curl -X POST http://127.0.0.1:8015/agent/chat \
  -H "Content-Type: application/json" -d '{"message": "公司的报销流程是什么"}'

# bob 问机密问题：诚实回答“资料不足”，不编造
curl -X POST http://127.0.0.1:8015/agent/chat \
  -H "X-API-Key: operator-key" -H "Content-Type: application/json" \
  -d '{"message": "产品路线图三季度上线什么功能"}'
```

### 8. 跑评测

```bash
curl -X POST http://127.0.0.1:8015/eval/run
curl -X POST -H "X-API-Key: operator-key" http://127.0.0.1:8015/eval/run
```

alice recall@3 = 1.0（6/6），bob = 0.833（5/6，看不到私有文档的那条失败）。**同一个评测，不同身份结果不同**——这提醒你评测要贴近真实权限环境。

### 9.（可选）上传自己的文件

在 `/docs` 里打开 `POST /documents/upload`，选择 `sample_docs` 里的任意文件，或自己写一个 txt 试试。可以故意传空文件、未知格式，看接口返回的友好错误。

## 代码阅读路线

```text
必须精读：
- main.py 的 /search 接口（看到粗排和精排的 DTO 怎么组装）
- main.py 的 /documents/upload 接口（看到文件处理全流程）
- retriever.py 的 search_chunks()（权限过滤 + metadata + 粗排）
- reranker.py 的 rerank()（精排打分逻辑）
- permissions.py 的 can_view_document()（数据级权限的核心判断）

可以粗读：
- settings.py / database.py / schemas.py（都是约定俗成的分层，看懂了不深究）
- document_processor.py（了解解析器选择逻辑即可，pdf 细节不用背）
- eval_runner.py（理解“评测 = 数据 + 运行 + 指标”就行）
- provider.py 的 DeepSeek 分支（真实 function calling，mock 下不看也不影响理解）

暂时不用管：
- main.py 的 /demo/seed-docs（它的逻辑和 upload 一样，只是从本地读文件）
- tools.py / tool_registry.py（模块 10-13 已经见过工具模式）
- chunker.py 的分词细节（模块 13 讲过，本模块只是复用）
```

如果只能花 30 分钟，最该看这条链路：

```text
POST /search
-> main.py search()
-> rag.py run_rag_search()      把“检索+精排+过滤”串成流水线
-> retriever.py search_chunks() 权限 + metadata + 粗排
-> reranker.py rerank()         精排（为什么顺序变了）
```

## 本模块的核心知识点（记住这 5 条就够面试用）

1. **文件解析是 RAG 的第一步，也是最容易踩坑的**：编码、空文件、未知格式都要处理，宁可报错也不要静默返回空文档。
2. **metadata 过滤和关键词检索是两回事**：前者是硬条件（WHERE 里过滤），后者是软条件（打分）。过滤要在打分之前，缩小范围。
3. **权限隔离必须在 SQL 层**：只查用户有权限的数据，而不是全量捞出来再过滤。文档权限（能看哪些文档）和工具权限（能调哪些工具）是两类权限。
4. **RAG 是两阶段检索**：粗排（召回 top-k，要广）→ 精排（rerank 取 top-n，要准）。粗排按共现数量，精排综合覆盖率、位置、标题、长度。
5. **检索到内容 ≠ 检索到正确答案**：必须加相关性阈值，低分巧合命中不进回答，否则模型会基于无关材料自信地编答案。

## 真实项目怎么做 vs 本模块简化了哪些

| 能力 | 真实项目 | 本模块教学版 |
|------|---------|-------------|
| 文件解析 | 全格式支持（Word/PPT/Excel/扫描 PDF OCR），清洗复杂 | 只支持 txt/md/pdf，PDF 用 pypdf，其余格式明确报错 |
| 切分 | 重叠窗口、按 Markdown 标题分节、按语义切 | 段落优先 + 超长按句子切，无重叠 |
| embedding | 向量化检索（模块 08 已学） | 继续用 bigram 关键词（教学版够用） |
| rerank | bge-reranker / Cohere Rerank 等深度模型 | 启发式打分（覆盖率/位置/标题/长度） |
| 权限 | 部门树、共享成员表、RBAC + 数据级权限 | 两级可见范围（public/private）+ owner |
| metadata | PostgreSQL JSONB 任意键值 | 两个固定字段（category / tags） |
| 评测 | 多指标、多版本对比、线上回流 | 单指标 recall@n，无历史保存 |

**哪些是必须理解的企业级方向**：权限隔离、metadata 过滤、rerank、相关性阈值、评测数据。**哪些只是为了跑通示例**：bigram 分词、启发式打分公式的具体权重。

## 练习任务（每个都对应真实工程能力）

### 练习 1：补上“分享可见”能力（权限设计）

现在 `private` 文档只有 owner 和 admin 能看到。真实项目里还有“共享给某人”的场景。给 `permissions.py` 增加一个字段/规则，让 alice 能把《产品路线图》显式共享给 bob，bob 之后就能检索到它。

要求：能通过接口验证——共享前 bob 检索不到，共享后 bob 检索得到；未共享的其他文档 bob 依然看不到。

提示：这涉及“新增一个存储字段 + 改权限判断 + 改接口”，就是真实项目里加一个数据权限规则的完整流程。

### 练习 2：调相关性阈值，观察模型回答变化（防幻觉）

`RAG_MIN_SCORE` 默认 0.25。把它调成 0.1 和 0.5，分别用 bob 问“产品路线图三季度上线什么功能”，观察回答：

- 阈值过低时，低分巧合片段又回到回答里（模型开始“自信地答错”）；
- 阈值过高时，正常检索结果也被过滤（回答变得过分保守）。

要求：解释为什么阈值是个“左右为难”的工程参数，以及真实项目里一般怎么标定它。

### 练习 3：往评测集里加一个 case，证明一次检索改动（评测）

给 `eval_cases.json` 加一条 case，例如 `"query": "打车费每次上限多少"`，期望命中《公司报销流程》。跑 `/eval/run`，观察它通过。然后做一个检索改动——比如把 `retriever.py` 的粗排改成只看“首段命中”（只统计前 100 字的 bigram），再跑评测，观察 recall 下降。

要求：用数字而不是感觉说明“改动变好还是变坏”。这就是评测存在的意义。

### 练习 4：上传一个“带元信息但检索不到”的文档（暴露真实问题）

上传一篇内容里**没有**当前任何关键词的文档（例如关于“公积金”的文档，而知识库里没有相关词），然后用 `POST /search` 和 `/agent/chat` 分别试。解释：

- 为什么关键词检索找不到它？（提示：embedding 检索正是为这个场景准备的）
- 此时 `/agent/chat` 返回什么？这是 RAG 的正确行为还是缺陷？

### 练习 5：给上传加一个“文档类型校验”业务规则（接口完善）

真实项目里，财务分类的文档可能只允许 admin 上传，普通用户不能上传财务文档。给 `POST /documents/upload` 加这个规则：

- 普通用户上传 `category=财务` 时返回 403；
- admin 上传财务文档正常。

要求：想清楚校验应该放在接口层还是权限层，并解释理由。

## 学完后你能讲什么（面试 / 简历素材）

- 能画出 RAG 从文件到回答的完整链路：上传 → 解析 → 切分 → 入库 → 权限/元数据过滤 → 检索 → rerank → 相关性阈值 → 带 sources 回答。
- 能讲清楚“权限过滤为什么必须在 SQL 层”以及文档权限和工具权限的区别。
- 能解释“两阶段检索”和“相关性阈值防幻觉”这两个面试高频考点。
- 能说出评测数据的价值和 recall@n 的含义，以及“为什么评测要带用户身份”。
- 能指出教学版简化在哪（关键词替代 embedding、启发式替代深度 rerank），说明你清楚真实项目和教学版的边界。

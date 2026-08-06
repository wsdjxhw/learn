# 生产级 RAG 工程 · 代码讲解

这份文档按**核心链路**解释代码结构，不是逐行读代码。读之前先看一眼文件总览，然后顺着 4 条链路读，每条链路读 2-4 个函数就够了。文件内的详细中文注释是给“卡住时”看的，不需要一遍全读。

---

## 0. 文件总览（先知道每层干嘛的）

```text
main.py                 接口层：HTTP 入口，所有路由都在这里，参数从 HTTP 来
schemas.py              DTO 层：请求/响应数据结构（Pydantic）
settings.py             配置层：从 .env 读配置
database.py             数据库：引擎 + 会话依赖 get_db()
models.py               ORM 层：documents / chunks 两张表
permissions.py          权限层：API Key -> 用户身份 + 文档级权限判断
document_processor.py   解析层：文件字节 -> 纯文本
chunker.py              切分层：文本 -> 多个片段
retriever.py            检索层：权限+metadata 过滤 + bigram 粗排
reranker.py             精排层：对候选重新打分排序
rag.py                  编排层：把检索+精排+过滤拼成一条流水线
tool_registry.py        工具声明：search_documents 的 schema
tools.py                工具执行：真正跑检索
provider.py             模型层：mock/DeepSeek 决策与回答
eval_runner.py          评测：跑 eval_cases.json 输出 recall@n
eval_cases.json         评测数据：问题 + 期望文档
```

依赖关系（谁 import 谁）大致是：

```text
main.py
  -> rag.py -> retriever.py / reranker.py
  -> provider.py -> tools.py -> rag.py
  -> permissions.py / eval_runner.py / document_processor.py / chunker.py
```

**读代码的窍门**：先读 main.py 的接口，看参数从哪里来；再顺着调用往下读。不要从第一个文件第一行读到最后一个文件最后一行。

---

## 1. 链路一：文件从上传到入库

### 入口：main.py 的 `POST /documents/upload`

```text
file: UploadFile = File(...)     <- 文件，来自 multipart/form-data
title/category/tags/visibility   <- metadata，来自同一个表单的文本字段
user: User = Depends(get_current_user)  <- 当前用户，来自 X-API-Key 头
db: Session = Depends(get_db)    <- 数据库会话，FastAPI 自动注入
```

**参数来源是初学者最容易卡的点**。一个文件上传接口里其实混了三类参数：文件（UploadFile）、普通文本（Form）、依赖注入（Depends）。它们来自不同的地方，但都写在函数签名里，FastAPI 根据类型和默认值自动区分。

**接口内做了什么**（就 5 步）：

1. 校验 `visibility` 只能 public/private；
2. `file.file.read()` 读字节，超 2MB 报 413；
3. `extract_text()` 解析成纯文本，失败转成 400；
4. `split_text()` 切分；
5. 写 `documents` 行 + 多个 `chunks` 行，一个事务提交。

**关键语法**：`db.flush()` 在 commit 之前把 `doc.id` 生成出来，因为后面建 chunk 需要 `document_id`。`db.refresh(doc)` 把数据库生成的时间字段同步回对象。

### 解析层：document_processor.py

核心是 `extract_text(filename, content) -> (text, content_type)`：

```text
按扩展名（.lower() 防大小写）选择解析器
  .txt/.md  -> _parse_text：UTF-8 解码失败回退 GBK
  .pdf      -> _parse_pdf：pypdf 提取文本，可选依赖 try/except
  其他      -> 抛 DocumentParseError（宁可报错不静默）
```

**为什么要 try/except pypdf**：让“没装 pypdf”不拖垮整个服务，只有真解析 PDF 时才提示安装。这是真实项目“可选依赖”的标准做法。

**为什么自定义 `DocumentParseError`**：main.py 能根据它转成清晰的 400，而不是把 Python 内部异常直接丢给前端。

### 切分层：chunker.py

`split_text(text, max_chars)` 三步：按空行拆段落 → 段落没超长直接留 → 超长按句末标点（。！？；）再切。`to_bigrams()` 把文本转成相邻两字，供检索用。

---

## 2. 链路二：检索 + 精排（本模块核心）

### 入口：main.py 的 `POST /search`

这个接口故意同时返回 `raw_candidates`（粗排）和 `reranked_results`（精排），让你直接对比顺序差异。

### 编排层：rag.py 的 `run_rag_search()`

这是整个 RAG 流水线的“指挥中心”，只做 4 件事：

```text
1. search_chunks()     召回：权限 + metadata 过滤 + bigram 粗排，取 top_k
2. rerank()            精排：对候选重打分，取 top_n
3. 相关性阈值过滤       精排分 < min_score 的片段不进 sources/上下文
4. 构造 sources 列表    （前端依据）和 context_text（喂给模型）
```

**为什么让 rag.py 当指挥中心**：没有它，/search、/tool/run、/agent/chat 三个入口都要重复写“检索→精排→过滤”。它把这条流水线收成一个函数，上层只调它。

### 检索层：retriever.py 的 `search_chunks()`

**权限过滤在 SQL 之前还是之后？** 本模块为了讲清楚，是“先查文档集合 → 再用 can_view_document 过滤 → 再查这些文档的 chunk”。注释里反复强调：**真实项目会把这个条件直接写进 WHERE**，原理相同，性能和安全更好。这个点面试必问。

```text
_visible_documents()       拿可见文档（can_view_document 逐个判断）
_filter_by_metadata()      category 精确匹配 + tags 包含任一
visible_ids               只有“过滤后可见”文档的 chunk 才允许进入检索
bigram_overlap()           粗分：查询和 chunk 共现多少个相邻两字
按粗分排序取 top_k
```

### 精排层：reranker.py 的 `rerank()`

对每个候选算 4 个信号再合成：

```text
final = 0.5*覆盖率 + 0.2*位置 + 0.2*标题命中 + 0.1*长度
覆盖率 < 0.2 时 final*0.3（覆盖率是硬信号，太低是巧合匹配）
```

**为什么不逐行解释每个信号**：你已经能从函数名 `_coverage_score` / `_position_score` / `_title_score` / `_length_score` 猜到各自职责。值得理解的是三个设计思想：

1. **覆盖率为什么占一半**：它是“相关性”最硬的信号，位置/标题只是辅助；
2. **覆盖率下限降权为什么存在**：防止“只覆盖 1/12 关键词但位置靠前”的巧合匹配（就是“度规”那个例子）；
3. **reasons 列表为什么要返回**：每个结果带“为什么这个分”，这是调试入口——排序不对时能看出哪个信号拖了后腿。

---

## 3. 链路三：权限（和前面模块最不一样的地方）

### permissions.py

两个核心函数：

```text
get_current_user(api_key)      依赖注入：API Key -> User(user_id, role)
can_view_document(user, doc)   admin 全可见；public 所有人可见；private 仅 owner
can_delete_document(user, doc) 删除比查看更严：仅 owner 或 admin
```

**为什么有权限层而不是在接口里写 if**：权限规则被检索（retriever）、详情（get_document）、删除（delete_document）多处复用。收进一个文件，改一处全生效。

**和模块 10-12 的 permissions 区别**：那里管“工具权限”（能不能调某工具），这里管“数据权限”（能看哪些文档）。代码里的 `User` 类和角色名沿用了模块 10 的命名，但含义不同——这是刻意保留的区分点，帮助你在脑子里建立“两类权限”的模型。

### 权限如何进入检索（重点）

`retriever._visible_documents` → `can_view_document`。效果：

- bob 的检索根本不会拿到 alice 的 private 文档的 chunk；
- bob 的 `/agent/chat` 决策（`_decide_mock`）也只看 bob 可见的文档，所以不会“假装知识库有内容”。

**权限不是检索之后的补充过滤，而是从源头隔离**——这是本模块最值得记住的一句话。

---

## 4. 链路四：Agent 决策 + 回答（provider.py）

`run_agent_chat(db, user, message)` 是唯一入口，按 MODEL_MODE 分支：

### mock 路径（默认）

```text
_decide_mock() 返回三态：
  idle    （共现=0）  -> 闲聊，不检索
  no_data （共现=1）  -> 知识问题但库里没料，诚实说资料不足
  search  （共现>=2） -> 执行检索
```

**为什么用三态而不是两态**：真实 RAG 里“不该检索”和“该检索但没结果”是两种情况。两态会把它们混成一种，导致知识问题检索不到时用低分片段硬答（就是修复前 bob 问机密问题的 bug）。

检索后还有两道保险：

1. `min_score` 相关性阈值过滤低分片段；
2. `sources` 为空时返回“资料不足”，而不是用碰巧命中的无关片段回答。

### DeepSeek 路径（真实模式）

`_deepseek_chat()` 是真实的 function calling 循环：

```text
第一次调用：system + user + tools 发给模型
  -> 模型返回 tool_calls（要检索）或直接回答
执行工具 -> 结果以 role=tool 回给模型
第二次调用：模型基于工具结果生成最终回答
```

**核心机制**：模型第一次回答时看不到检索结果，必须把工具输出“回喂”给模型，它才能基于资料组织回答。这就是 Agent 循环里“观察（observation）”的体现。

---

## 5. 链路五：评测（eval_runner.py + eval_cases.json）

`run_eval(db, user, top_n)`：

```text
读 eval_cases.json 的 cases
对每个 case：run_rag_search(query) 拿最终 sources
  期望文档标题是否出现在 returned_titles 里 -> hit
统计 recall@n = 通过数 / 总数
```

**为什么要 user 参数**：同一个 case，admin 能看到私有文档、bob 看不到。评测带身份，结果才贴近真实环境。

**教学版评测简化**（README 里有完整表）：只用“文档标题是否出现”判断命中，没有判断“片段是否真正回答问题”；不保存历史，无法对比版本。这些就是模块 21 评测要做的事。

---

## 6. 如果要改一个需求，改哪些文件

这是检验你是否读懂了分层的标准方式：

| 需求 | 改哪个文件 |
|---|---|
| 增加一种文件格式（如 .docx） | document_processor.py 加分支 |
| 调整切分长度 | settings.py 的 `CHUNK_MAX_CHARS` |
| 加一种 metadata 字段（如作者） | models.py + schemas.py + retriever 过滤 |
| 新增“共享给某人”权限 | permissions.py + models.py + 一个接口 |
| 调整 rerank 权重 | reranker.py |
| 调整相关性阈值 | settings.py 的 `RAG_MIN_SCORE` |
| 加一条评测 case | eval_cases.json |
| 改 Agent 的检索决策 | provider.py 的 `_decide_mock` |

如果需求要动 3 个以上的层，说明它在真实项目里就是个“跨层改动”——这也是面试常被问的“你的项目分层怎么体现的”。

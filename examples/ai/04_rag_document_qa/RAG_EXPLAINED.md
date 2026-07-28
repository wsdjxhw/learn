# 逐段讲解

这一节开始学习 RAG。

## RAG 解决什么问题

普通聊天接口只能基于模型已有知识回答。

但很多 AI 应用需要基于你自己的资料回答，例如：

- 公司文档
- 产品说明
- 课程笔记
- PDF 内容
- 本地知识库

RAG 的思路是：

```text
先从资料里检索相关片段，再把片段交给模型回答
```

## 文件分工

`main.py`

接口层，负责：

- 接收文档
- 接收文件上传
- 接收问题
- 返回答案和来源

`db.py`

数据层，负责：

- 保存 documents
- 保存 chunks
- 查询 chunks

`text_splitter.py`

文本切分层，负责把长文档切成多个 chunk。

`retriever.py`

检索层，负责从 chunks 里找出和问题最相关的片段。

`provider.py`

模型层，负责 mock 或 DeepSeek 回答。

## RAG 链路

```text
文档内容
-> split_text()
-> chunks
-> 保存到 SQLite
-> 用户提问
-> retrieve_relevant_chunks()
-> 相关 chunks
-> generate_answer()
-> 返回 answer 和 sources
```

## 什么是 chunk

chunk 就是文档片段。

如果文档很长，直接发给模型会有几个问题：

- 上下文可能超长。
- 成本更高。
- 无关内容会干扰回答。

所以要先切分，再只检索相关片段。

## 什么是 sources

`sources` 是回答引用的资料来源。

它让你知道：

- 模型参考了哪篇文档。
- 模型参考了哪个 chunk。
- 这个 chunk 的内容是什么。

真实 AI 应用里，返回 sources 很重要，因为用户需要判断答案有没有依据。

## 当前版本为什么不用向量库

当前版本先不用 embedding 和向量库。

原因是入门阶段先掌握流程更重要：

```text
切分 -> 存储 -> 检索 -> 生成 -> 引用来源
```

后面再把 `retriever.py` 里的关键词检索，替换成 embedding + 向量库检索。

## 和 Java 的类比

```text
main.py          -> Controller
db.py            -> Repository / DAO
text_splitter.py -> 文本处理工具类
retriever.py     -> 检索 Service
provider.py      -> 模型调用 Service
BaseModel        -> Request DTO
```

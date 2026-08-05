# 先从这里开始

本模块学习 Agent 记忆基础。

如果你刚学完 `07_short_term_state`，请先建立一个边界：

- 短期状态：一次 Agent run 当前执行到哪一步。
- 聊天历史：用户和助手原始说过什么。
- 长期记忆：从历史里筛选、压缩、结构化后，未来值得复用的信息。

推荐阅读顺序：

1. `README.md`：先跑起来，按接口顺序观察结果。
2. `MEMORY_BASICS.md`：理解长期记忆的基础概念。
3. `MEMORY_BASICS_EXPLAINED.md`：逐段看代码职责。
4. 再打开 `main.py`、`memory_extractor.py`、`memory_store.py` 对照阅读。

第一次运行不需要 API Key，默认 mock 模式即可。

# 先从这里开始

本模块学习 Agent 记忆治理。

你在 `08_memory_basics` 已经学过：

- 从对话中提取长期记忆。
- 保存结构化 memory。
- 后续请求检索并复用 memory。

现在要补上真实项目必须有的治理能力：

- 用户能查看自己的记忆。
- 用户能删除错误或不想保留的记忆。
- 过期记忆不能继续影响回答。
- 密码、API Key、身份证号、银行卡号、验证码这类敏感信息不能写入长期记忆。
- 记忆的创建、更新、删除、过期、使用要能留下审计线索。

推荐阅读顺序：

1. `README.md`：先启动服务，按接口顺序测试。
2. `MEMORY_GOVERNANCE_BASICS.md`：理解治理规则解决什么工程问题。
3. `MEMORY_GOVERNANCE_EXPLAINED.md`：逐段看代码结构。
4. 再打开 `memory_safety.py`、`memory_store.py`、`main.py` 对照阅读。

第一次运行不需要 API Key，默认 mock 模式即可。

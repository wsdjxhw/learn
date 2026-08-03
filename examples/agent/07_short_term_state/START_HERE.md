# 学习入口

先按这个顺序学习：

1. 阅读 `README.md`，跑通所有接口。
2. 阅读 `SHORT_TERM_STATE_BASICS.md`，理解 run、step、聊天历史、长期记忆的区别。
3. 打开 `main.py`，看请求如何进入系统。
4. 打开 `agent_runner.py`，看 Agent 如何逐步写入状态。
5. 打开 `state_store.py`，看数据库状态如何保存和转换成响应 DTO。
6. 阅读 `SHORT_TERM_STATE_EXPLAINED.md`，补齐代码细节。

本模块最重要的验收标准：

- 你能解释 `run_id` 为什么存在。
- 你能解释 `agent_runs` 和 `agent_steps` 两张表分别保存什么。
- 你能通过制造失败，看到失败前已完成的步骤仍然保存在数据库里。
- 你能说清楚短期状态和聊天历史为什么不能混为一谈。

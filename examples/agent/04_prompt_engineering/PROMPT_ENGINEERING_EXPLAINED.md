# 提示词工程代码讲解

## 1. main.py：接口层

`main.py` 定义了这些接口：

- `GET /health`：查看服务状态和默认 prompt 版本。
- `GET /tools`：查看工具清单。
- `GET /prompts`：查看所有 prompt 版本。
- `GET /prompts/{version}`：查看某个 prompt 的完整内容。
- `POST /agent/run`：用某个 prompt 版本运行 Agent。
- `POST /agent/compare`：用同一份输入对比多个 prompt 版本。

`PromptRunRequest` 是请求体 DTO，类似 Java 里的 Request DTO。

其中：

```python
prompt_version: str | None = None
```

表示这个字段可以是字符串，也可以为空。

如果它为空，代码会使用：

```python
prompt_version = payload.prompt_version or get_prompt_version()
```

这行的意思是：请求体传了版本就用请求体；没传就用 `.env` 默认版本。

## 2. settings.py：读取配置

`settings.py` 使用：

```python
load_dotenv()
```

读取 `.env` 文件。

本模块有两个配置：

- `PROMPT_VERSION`：默认 prompt 版本。
- `PROMPT_DIR`：prompt 文件目录。

如果没有 `.env`，代码也能运行，因为 `os.getenv()` 提供了默认值。

## 3. prompt_store.py：管理 prompt 文件

`prompt_store.py` 负责三件事：

- 找到 prompt 文件路径。
- 列出所有 prompt 版本。
- 读取某个 prompt 的完整内容。

`Path(__file__).parent` 表示当前 Python 文件所在目录。

本模块用它来保证无论你从哪里启动 Python，都能定位到模块自己的 `prompts/` 目录。

`list_prompt_versions()` 使用：

```python
for prompt_path in sorted(prompt_dir.glob("*.md")):
```

这会遍历所有 `.md` prompt 文件。

`sorted()` 是为了让返回顺序稳定，方便对比。

## 4. PROMPT_BEHAVIOR 是什么

prompt 文件里有一行：

```text
PROMPT_BEHAVIOR: TOOL_FIRST
```

这不是生产项目的必要写法，而是本模块的教学标记。

`mock_model.py` 会读取这个标记，稳定模拟不同 prompt 的行为：

- `DIRECT_ANSWER`：直接回答，不调用工具。
- `TOOL_FIRST`：先调用工具，再生成回答。

真实模型不会这么机械，但这个标记能让学习者稳定看到 prompt 版本差异。

## 5. mock_model.py：模拟模型决策

`decide_actions(prompt, case)` 接收：

- `prompt`：从 prompt 文件读取出来的内容。
- `case`：用户输入和订单信息。

如果 prompt 行为是 `DIRECT_ANSWER`，它返回：

```python
{
    "decision_type": "final_answer",
    "tool_calls": []
}
```

如果 prompt 行为是 `TOOL_FIRST`，它返回：

```python
{
    "decision_type": "tool_plan",
    "tool_calls": [...]
}
```

这就是“prompt 影响工具选择”的最小可运行版本。

## 6. agent.py：把 prompt、模型和工具串起来

`run_agent_with_prompt(case, prompt_version)` 是核心函数。

它的流程是：

```text
读取 prompt
-> mock model 决策
-> 如果直接回答，就返回 answer
-> 如果需要工具，就逐个执行工具
-> 根据工具结果生成最终回答
```

`steps` 会记录：

- 使用了哪个 prompt 版本。
- prompt 行为是什么。
- 模型为什么这样决策。
- 调用了哪些工具。
- 每个工具的输入、输出和耗时。

这些记录是后续做 prompt 测试和评测的基础。

## 7. tools.py：prompt 不是安全边界

即使 prompt 写了“不允许调用未知工具”，后端仍然必须做工具白名单。

原因是：

- 模型可能输出错误工具名。
- prompt 可能被改坏。
- 用户输入可能诱导模型越界。

所以 `run_tool()` 只允许执行代码里明确列出的工具。

这条原则后面在 Agent 安全模块会继续展开。

## 8. 推荐阅读顺序

建议按这个顺序看：

1. 先看 `prompts/v1_direct_answer.md` 和 `prompts/v2_tool_first.md`。
2. 再看 `main.py` 的接口。
3. 再看 `prompt_store.py` 如何加载 prompt。
4. 再看 `mock_model.py` 如何模拟不同行为。
5. 最后看 `agent.py` 如何执行工具并记录 steps。

先理解 prompt 版本和对比方法，再去关心真实模型接入，会更稳。

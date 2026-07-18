# 从这里开始

如果你现在的感觉是“我不知道先学哪个文件、先看哪一段、先敲什么”，那就先忽略别的内容，只做这一页。

目标不是“今天学会 Python”，而是先完成第一个最小闭环：

1. 打开一个 Python 文件
2. 看懂它的大概结构
3. 亲手运行它
4. 自己改动它
5. 再运行一次

只要你能完成这 5 步，你就已经开始了。

## 今天只做这一件事

只看这个文件：

- [examples/python/01_text_tool.py](C:/Users/wsdjx/Desktop/learn/examples/python/01_text_tool.py:1)

配套讲解只看这个文件：

- [examples/python/01_text_tool_EXPLAINED.md](C:/Users/wsdjx/Desktop/learn/examples/python/01_text_tool_EXPLAINED.md:1)

今天不要看 Go，不要看 FastAPI，不要看 AI 接口。

## 第一步：先运行

在当前目录执行：

```powershell
python examples/python/01_text_tool.py
```

你应该会看到类似输出：

```text
Text summary:
- char_count: 63
- word_count: 10
- line_count: 1
- preview: Python is a good first language for AI application developme
```

如果能看到输出，说明你已经完成了第一关：`Python 能跑起来`。

## 第二步：只理解 3 个问题

第一次看代码时，不要试图每一行都懂。你只回答这 3 个问题：

1. 程序输入是什么
2. 程序处理了什么
3. 程序输出是什么

对这个文件来说：

- 输入：一段文本
- 处理：统计字符数、单词数、行数，并截取预览
- 输出：打印统计结果

只要你能说出这三句话，就已经是“看懂一个程序”了。

## 第三步：自己改 3 次

不要只读。你必须修改它。

按顺序做这 3 个改动：

1. 把默认文本改成你自己的句子
2. 给返回结果里新增一个字段，例如 `is_long_text`
3. 把 `preview` 的长度从 `60` 改成 `20`

每改一次，就重新运行一次。

## 第四步：把这个文件重写一遍

不要复制粘贴，自己新建一个文件，例如：

- `examples/python/my_text_tool.py`

然后自己从空白开始重写下面这几个部分：

- 一个函数
- 一个 `main()`
- 一个 `if __name__ == "__main__":`

哪怕你要一边看一边写也没关系。这个动作比继续看 10 个新知识点更重要。

## 明天做什么

明天再看这个：

- [examples/python/02_http_json.py](C:/Users/wsdjx/Desktop/learn/examples/python/02_http_json.py:1)

目标只定一个：

- 看懂“Python 怎么请求一个 HTTP API，再把 JSON 变成 Python 数据”

## 后天做什么

后天再看这个：

- [examples/python/03_fastapi_app/main.py](C:/Users/wsdjx/Desktop/learn/examples/python/03_fastapi_app/main.py:1)

目标只定一个：

- 看懂“Python 怎么把一个脚本变成 Web API”

## 你这一周真正的学习顺序

第 1 天：
- 跑 `01_text_tool.py`
- 改 3 次
- 自己重写一次

第 2 天：
- 跑 `02_http_json.py`
- 学会 `JSON`、`HTTP`、异常处理

第 3 天：
- 跑 `03_fastapi_app/main.py`
- 学会接口、请求体、返回值

第 4 天：
- 自己写一个“输入一句话，返回字数统计”的脚本

第 5 天：
- 自己给 FastAPI 加一个新接口

第 6 天：
- 复习前 5 天，重写一遍核心代码

第 7 天：
- 再进入 Go

## 你现在不要做的事

先不要做这些：

- 不要同时学 Python 和 Go 细节
- 不要刷一堆语法视频
- 不要一开始就上 LangChain
- 不要碰复杂 Agent 框架
- 不要试图一周内学完后端、前端、模型、部署

## 判断自己有没有学会

你今天学会的标准不是“全部记住”，而是能做到下面任意 3 条：

- 能运行 `01_text_tool.py`
- 能解释输入、处理、输出
- 能改动一个字段
- 能新增一个字段
- 能自己重写一个简化版

做到这一步，你就不是“无从学起”，而是已经起步了。

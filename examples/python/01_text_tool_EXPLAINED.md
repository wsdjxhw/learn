# `01_text_tool.py` 逐段讲解

这个文件的作用很简单：给一段文本做最基础的统计。

你现在不要想“这和 AI 有什么关系”。先学会最基本的文本处理，因为后面的 AI 应用本质上也在做这几件事：

- 接收文本
- 处理文本
- 返回结果

## 先看完整代码结构

这个文件可以分成 4 段：

1. 导入工具
2. 定义一个处理文本的函数
3. 定义一个程序入口 `main()`
4. 告诉 Python：直接运行文件时就执行 `main()`

## 第 1 段：导入

```python
from pathlib import Path
```

意思：

- 从 Python 标准库里导入 `Path`
- `Path` 用来处理文件路径和文件读写

为什么不用更复杂的库：

- 因为你现在只需要“判断文件是否存在”和“读取文本内容”
- `Path` 已经足够

## 第 2 段：文本处理函数

```python
def summarize_text(text: str) -> dict:
```

意思：

- 定义一个函数，名字叫 `summarize_text`
- 它接收一个参数 `text`
- `text: str` 表示这个参数应该是字符串
- `-> dict` 表示它最后会返回一个字典

你可以把函数理解成：

- 输入一段文本
- 输出一个统计结果

这就是最基本的“输入 -> 处理 -> 输出”。

### 这几行在干什么

```python
words = text.split()
lines = text.splitlines()
```

意思：

- `split()`：按空白字符切开，得到单词列表
- `splitlines()`：按换行切开，得到每一行组成的列表

例如：

```python
"hello world".split()
```

会变成：

```python
["hello", "world"]
```

### 返回结果

```python
return {
    "char_count": len(text),
    "word_count": len(words),
    "line_count": len(lines),
    "preview": text[:60],
}
```

这里返回了一个字典。

每个字段的意思：

- `char_count`：字符总数
- `word_count`：单词总数
- `line_count`：总行数
- `preview`：前 60 个字符

这里你要学会两个东西：

1. `len(...)` 用来求长度
2. `text[:60]` 表示“切出前 60 个字符”

## 第 3 段：主函数

```python
def main() -> None:
```

`main()` 可以理解成程序真正开始执行的地方。

### 先准备文件路径

```python
sample_path = Path("sample.txt")
```

意思：

- 创建一个表示 `sample.txt` 的路径对象
- 这个文件如果存在，就优先读取它

### 判断文件是否存在

```python
if sample_path.exists():
    content = sample_path.read_text(encoding="utf-8")
else:
    content = "Python is a good first language for AI application development."
```

意思：

- 如果 `sample.txt` 存在，就读这个文件
- 如果不存在，就使用代码里默认写死的一段文本

这个写法很适合初学者，因为：

- 有文件时可以练习文件读写
- 没文件时也能直接运行成功

### 调用函数并打印结果

```python
result = summarize_text(content)
print("Text summary:")
for key, value in result.items():
    print(f"- {key}: {value}")
```

意思：

- `result = summarize_text(content)`：把文本交给函数处理
- `print("Text summary:")`：打印标题
- `for key, value in result.items()`：把字典里的每一项拿出来
- `print(f"- {key}: {value}")`：逐行打印

这里你要学的核心是：

- 函数调用
- `for` 循环
- 字典遍历
- 格式化字符串 `f"..."`

## 第 4 段：程序入口判断

```python
if __name__ == "__main__":
    main()
```

这是 Python 初学者最容易疑惑的一段，但你现在只要记住一句话：

- 直接运行这个文件时，就执行 `main()`

你暂时不需要深究模块导入机制。

## 你现在该怎么学这个文件

不要背代码，按这个顺序来：

1. 先运行一次
2. 只看 `summarize_text`
3. 再看 `main()`
4. 最后看 `if __name__ == "__main__":`

## 你必须做的练习

练习 1：
- 把默认文本换成中文

练习 2：
- 新增一个字段：`has_python`
- 如果文本里包含 `Python`，就返回 `True`

练习 3：
- 新增一个字段：`preview_10`
- 只显示前 10 个字符

练习 4：
- 如果文件存在，打印 `Loaded from file`
- 如果文件不存在，打印 `Using default text`

## 你做完这个文件后，应该真正学会什么

不是“学会 Python 了”，而是学会这几个非常具体的点：

- 怎么定义函数
- 怎么处理字符串
- 怎么返回字典
- 怎么写 `if`
- 怎么写 `for`
- 怎么打印结果
- 怎么组织一个最小脚本

这才是你继续学 API、FastAPI、AI 接口的基础。

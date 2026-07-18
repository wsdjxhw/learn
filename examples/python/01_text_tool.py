from pathlib import Path


def summarize_text(text: str) -> dict:
    # 这个函数是整个脚本的核心：
    # 输入一段文本，输出一个字典格式的统计结果。
    #
    # 你现在可以把它理解成一个“文本处理器”。
    # 后面做 AI 应用时，也经常会先拿到文本，再做处理，再返回结果。
    words = text.split()
    lines = text.splitlines()

    for w in words:
        if(w == "Python"):
            has_python = True
            break
        else:
            has_python = False

    return {
        # len(text) 统计整段文本的字符数。
        "char_count": len(text),
        # words 是 split() 之后得到的列表，长度就是“单词数”。
        "word_count": len(words),
        # lines 是按换行切开的列表，长度就是“行数”。
        "line_count": len(lines),
        "has_python": has_python,
        # text[:60] 表示截取前 60 个字符，常用于做预览。
        "preview_10": text[:10],
        "preview": text[:60],
    }


def main() -> None:
    # main() 是程序入口。
    # 你可以把它理解成：程序启动后，先做哪些步骤。

    # 先准备一个路径对象，表示当前目录下的 sample.txt。
    sample_path = Path("examples\python\sample.txt")

    if sample_path.exists():
        # 如果 sample.txt 存在，就优先读取这个文件。
        content = sample_path.read_text(encoding="utf-8")
        print("Loaded from file")
    else:
        # 如果文件不存在，就用一段默认文本，这样脚本依然可以直接运行。
        content = "Python is a good first language for AI application development."
        print("Using default text")

    # 调用前面定义的函数，得到统计结果。
    result = summarize_text(content)
    print("Text summary:")

    # result 是一个字典，这里把每个字段逐行打印出来。
    for key, value in result.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    # 直接运行这个文件时，执行 main()。
    main()

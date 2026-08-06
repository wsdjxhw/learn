"""
document_processor.py - 文档解析层

职责：把“用户上传的原始文件字节”变成“干净的纯文本”。
     这是真实 RAG 项目的第一步，也是最容易踩坑的一步：
     文件可能有编码问题、空内容、未知格式、超大体积。

处理流程（本模块）：
    原始文件名 + 文件字节 -> 按扩展名选择解析器 -> 纯文本 + content_type

真实项目里这一步会复杂很多：
- PDF：扫描件要先 OCR；带表格的要用表格解析库；页眉页脚要去掉；
- Word / PPT / Excel：要转成文本或 HTML 再清洗；
- 网页 / 邮件：要剥掉标签、CSS、导航栏；
- 语音 / 视频：走语音识别（ASR）。
教学版先覆盖 txt / md / pdf 三种常见格式，其余格式给出清晰报错而不是静默失败。

关于“静默失败”：真实系统最怕“看起来成功了，其实内容丢了”。
所以解析器宁可报错，也不要返回空文本，这一点会在 main.py 的上传接口里做兜底。
"""
from typing import Tuple

# 用可选导入处理 PDF。为什么 try/except？
# pypdf 是纯 Python 库，绝大多数环境装了就能用；
# 但为了让“没装 pypdf 也能启动整个服务”，我们把导入失败做成“功能降级”，
# 只有真解析 PDF 时才提示安装。这就是真实项目里“可选依赖”的标准做法。
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


class DocumentParseError(Exception):
    """文档解析失败的自定义异常。

    为什么自定义异常而不是直接抛 ValueError？
    这样 main.py 可以根据异常类型返回清晰的 HTTP 错误，
    而不是把 Python 内部报错直接丢给前端。
    """


def extract_text(filename: str, content: bytes) -> Tuple[str, str]:
    """根据文件扩展名解析文件，返回 (纯文本, content_type)。

    参数：
        filename: 原始文件名（含扩展名），用来判断解析器。
        content: 文件原始字节（bytes）。前端上传的文件在 FastAPI 里是 UploadFile，
                 这里接收的是已经 read() 出来的字节串。

    返回：
        (text, content_type)：text 是清洗后的纯文本；content_type 记录格式，
        例如 "text/plain" / "text/markdown" / "application/pdf"。

    为什么要返回 content_type？
    后续切分、展示、检索日志都可能需要知道来源格式，
    比如 PDF 文本常带多余换行，清洗策略和 txt 不同。
    """
    # 文件可能带路径，只取最后的文件名。os.path.basename 处理不同系统的分隔符。
    import os
    name = os.path.basename(filename)
    # lower() 避免 ".TXT" 这类大写扩展名匹配不上
    ext = os.path.splitext(name)[1].lower()

    if not content:
        # 空文件：真实项目里必须拦截。检索一个空文档等于没检索，还会污染结果。
        raise DocumentParseError("文件内容为空，无法解析")

    if ext in (".txt", ".md", ".markdown"):
        text = _parse_text(content, name)
        content_type = "text/markdown" if ext in (".md", ".markdown") else "text/plain"
        return text, content_type

    if ext == ".pdf":
        return _parse_pdf(content, name)

    # 未知格式：明确报错，而不是假装成功。这是教学版故意保留的“错误路径”。
    raise DocumentParseError(
        f"暂不支持 {ext or '无扩展名'} 格式。本教学模块支持：.txt / .md / .pdf。"
    )


def _parse_text(content: bytes, name: str) -> str:
    """解析纯文本文件。

    关键坑：字节 -> 字符串需要“解码”，而文件本身不声明自己的编码。
    - 绝大多数中文 txt/md 文件是 UTF-8；
    - 但有少量老文件是 GBK/GB2312。
    真实项目通用策略：先试 UTF-8，失败再回退到 GBK（errors 参数控制）。
    """
    try:
        # decode("utf-8")：把字节解码成 Python 字符串。
        # 类比 Java：new String(bytes, StandardCharsets.UTF_8)
        return content.decode("utf-8")
    except UnicodeDecodeError:
        # 解码失败说明不是 UTF-8，很可能是 GBK 中文编码。再试一次。
        return content.decode("gbk", errors="replace")


def _parse_pdf(content: bytes, name: str) -> Tuple[str, str]:
    """解析 PDF 文件。

    PDF 本身是排版二进制格式，必须靠库提取文本。
    这里用 pypdf（纯 Python、无系统依赖，最适合教学）。
    """
    if not HAS_PYPDF:
        # 功能降级提示：没装库时给出安装命令，而不是抛一个看不懂的异常。
        raise DocumentParseError(
            f"解析 PDF 需要 pypdf，请先执行：pip install pypdf"
        )
    try:
        # PdfReader 从内存字节读取（BytesIO 把 bytes 包装成文件流对象，
        # 因为 pypdf 接受文件对象或路径，不接受裸 bytes）。
        from io import BytesIO
        reader = pypdf.PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages:  # 遍历每一页
            # extract_text() 提取该页文本；可能为空（扫描件/纯图片 PDF）。
            pages.append(page.extract_text() or "")
        text = "\n\n".join(pages)  # 页与页之间加空行，方便后续按段落切分

        if not text.strip():
            # 提取出来是空的，多半是“扫描版 PDF”（纯图片）。
            # 这种必须走 OCR，教学版明确说明，而不是默默返回空文档。
            raise DocumentParseError(
                f"{name} 没有可提取的文本。如果是扫描版 PDF（图片），需要 OCR 支持，"
                f"教学版暂不处理。"
            )
        return text, "application/pdf"
    except DocumentParseError:
        raise
    except Exception as e:
        # pypdf 对损坏文件会抛各种底层异常，统一包成我们的业务异常，
        # 让接口层能返回友好错误。
        raise DocumentParseError(f"PDF 解析失败：{e}") from e

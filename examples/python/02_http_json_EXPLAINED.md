# `02_http_json.py` 逐段讲解

这个文件教你的不是 AI，本质上是 AI 应用里最常见的一步：

- 向外部服务发请求
- 拿到 JSON
- 变成 Python 数据
- 再处理结果

后面你调模型 API、调第三方服务、调自己写的后端接口，都是这个套路。

## 这个文件只有 3 个重点

1. 怎么发 HTTP 请求
2. 怎么把 JSON 变成 Python 对象
3. 请求失败时怎么处理错误

## 先运行

在工作区执行：

```powershell
python examples/python/02_http_json.py
```

如果网络正常，你会看到类似输出：

```text
Total posts: 100
[1] ...
[2] ...
[3] ...
```

## 第 1 段：导入

```python
import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
```

作用分别是：

- `json`：把 JSON 字符串转成 Python 数据
- `urlopen`：发起 HTTP 请求
- `HTTPError`、`URLError`：处理常见网络错误

## 第 2 段：请求并解析 JSON

```python
def fetch_json(url: str) -> list[dict]:
```

意思：

- 传入一个 URL
- 返回一个“列表，列表里每一项都是字典”

这里你不用纠结类型注解细节，只要知道：

- 返回值不是字符串了
- 返回值已经是 Python 可直接处理的数据

### 请求部分

```python
with urlopen(url, timeout=10) as response:
```

意思：

- 打开这个 URL
- 最多等 10 秒
- `response` 代表服务器返回的内容

### 读取内容

```python
data = response.read().decode("utf-8")
```

意思：

- `read()` 读出原始内容
- `decode("utf-8")` 把字节变成字符串

### 转成 Python 数据

```python
return json.loads(data)
```

意思：

- `loads` 会把 JSON 字符串转成 Python 对象

比如：

- JSON 数组 -> Python 列表
- JSON 对象 -> Python 字典

## 第 3 段：主函数

```python
url = "https://jsonplaceholder.typicode.com/posts"
```

这是一个公开测试接口，专门适合学习 HTTP 和 JSON。

### 为什么要 `try/except`

```python
try:
    posts = fetch_json(url)
except HTTPError as exc:
    ...
except URLError as exc:
    ...
```

网络请求和本地字符串处理不一样，它可能失败。

常见失败原因：

- 网络断开
- 地址错误
- 服务器报错
- 响应超时

所以这里先学会一个习惯：

- 只要发请求，就要考虑失败情况

### 结果处理

```python
print(f"Total posts: {len(posts)}")
for post in posts[:3]:
    print(f"[{post['id']}] {post['title']}")
```

这里你要看懂 3 件事：

1. `posts` 是一个列表
2. `post` 是列表里的一个字典
3. `post['id']` 和 `post['title']` 是取字典字段

## 你现在只回答这 3 个问题

1. 输入是什么  
   一个 URL

2. 处理是什么  
   发请求，读取返回内容，把 JSON 转成 Python 数据

3. 输出是什么  
   打印总条数和前 3 条标题

## 你现在必须做的练习

练习 1：
- 把打印前 3 条改成打印前 5 条

练习 2：
- 新增一行，打印第一条数据的 `body`

练习 3：
- 新增一个字段筛选，只打印 `userId == 1` 的前 3 条

练习 4：
- 把 URL 改错一次，故意触发异常，看看报错信息

## 这一课你真正学什么

不是“学会网络编程”，而是先掌握这几个很具体的能力：

- 知道 HTTP 请求是什么
- 知道 JSON 是什么
- 知道 JSON 怎么变成 Python 数据
- 知道列表和字典怎么配合使用
- 知道请求失败时不能让程序直接崩掉

# Go 最小基础

这份文档只解释本目录 01、02、03 会用到的 Go 概念。

目标不是学完整 Go 语言，而是先能读懂这些后端示例。

## `package main`

每个 Go 文件开头都有：

```go
package main
```

`package` 表示这个文件属于哪个包。

`main` 是特殊包名。一个可直接运行的 Go 程序通常需要：

```text
package main
func main()
```

可以先理解成 Java 里有 `public static void main(String[] args)` 的启动类。

## `import`

`import` 用来引入别的包。

例如：

```go
import "fmt"
```

`fmt` 用来格式化输出。

```go
import (
    "encoding/json"
    "net/http"
)
```

这是一次引入多个包。`net/http` 是 Go 标准库里的 HTTP 包。

## `func`

Go 用 `func` 定义函数：

```go
func buildTitle(question UserQuestion) string {
    return question.Text
}
```

含义是：

```text
函数名：buildTitle
参数：question，类型是 UserQuestion
返回值：string
```

类比 Java：

```java
String buildTitle(UserQuestion question) {
    return question.text;
}
```

## `struct`

Go 没有 Java 的 class 关键字。

最常见的数据结构是：

```go
type UserQuestion struct {
    ID int
    Text string
}
```

可以先理解成 Java 的简单 DTO / POJO。

## slice

slice 写法：

```go
questions := []UserQuestion{}
```

可以先理解成 Java 的 `ArrayList<UserQuestion>`。

它比数组更常用，因为长度可以变化。

## `:=`

`:=` 表示声明变量并赋值：

```go
name := "Tom"
```

Go 会自动推断 `name` 是 `string`。

如果变量已经声明过，通常用：

```go
name = "Jerry"
```

## `if`

Go 的 `if` 不需要小括号：

```go
if name == "" {
    name = "world"
}
```

这和 Java 不同。Java 通常写：

```java
if (name.equals("")) {
    name = "world";
}
```

## `for range`

遍历 slice 常用：

```go
for index, question := range questions {
    fmt.Println(index, question.Text)
}
```

`index` 是下标。

`question` 是当前元素。

如果不需要下标，可以写：

```go
for _, question := range questions {
    fmt.Println(question.Text)
}
```

`_` 表示这个值我不使用。

## 指针和 `&`

在 HTTP 示例里会看到：

```go
json.NewDecoder(request.Body).Decode(&payload)
```

`&payload` 表示把 `payload` 的地址传进去。

原因是 Decode 需要修改 payload，把 JSON 字段填进去。如果只传一个普通值，函数拿到的是副本，无法把结果写回原变量。

初学阶段先记住：

```text
需要让函数修改某个变量时，经常会传 &变量名
```

后面学到指针时再系统展开。

## JSON tag

Go struct 字段大写开头，但 JSON 字段通常小写：

```go
type ChatRequest struct {
    Message string `json:"message"`
}
```

`Message` 是 Go 字段名。

`json:"message"` 是 JSON 字段名。

所以接口请求体应该是：

```json
{
  "message": "hello"
}
```

## error

Go 很多函数会返回两个值：

```go
value, err := doSomething()
```

通常写法是：

```go
if err != nil {
    // 处理错误
    return
}
```

这和 Java 的 try/catch 不同。Go 更习惯显式检查错误。

## 学习建议

先不要一口气学完 Go 语法。

对这个项目来说，先看懂：

- struct
- slice
- func
- if
- for range
- JSON tag
- handler
- error

就足够进入 Go AI 网关模块。

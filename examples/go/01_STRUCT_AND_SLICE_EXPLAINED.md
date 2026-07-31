# 01 结构体和切片代码讲解

对应代码：

[01_struct_and_slice.go](01_struct_and_slice.go)

## 这个示例教什么

这个示例用“用户准备发给 AI 的问题”来讲 Go 最小语法。

它不是单纯打印书名，而是为后面的 HTTP 服务和 AI 网关铺垫：

```text
原始用户问题 -> 整理成摘要 -> 后续可以交给 API 或网关
```

## `package main`

文件第一行：

```go
package main
```

表示这是一个可运行程序的一部分。

如果要用：

```powershell
go run 01_struct_and_slice.go
```

就需要 `package main` 和 `func main()`。

## `UserQuestion`

```go
type UserQuestion struct {
    ID       int
    UserName string
    Text     string
    Tags     []string
    Urgent   bool
}
```

`struct` 可以先类比成 Java DTO / POJO。

字段含义：

- `ID`：问题编号。
- `UserName`：提问人。
- `Text`：问题正文。
- `Tags`：标签列表，类型是 `[]string`。
- `Urgent`：是否需要优先处理。

这里用 `Tags []string` 是为了提前接触 slice，因为后面 API 返回列表、batch 请求都会用到类似结构。

## `QuestionSummary`

`QuestionSummary` 是整理后的输出结构。

为什么不直接打印 `UserQuestion`？

因为真实项目里经常会区分：

```text
输入 DTO
处理后的业务结果
接口返回 DTO
数据库 Entity
```

这个示例先用很小的例子建立这种分层意识。

## `buildTitle()`

```go
func buildTitle(question UserQuestion) string
```

这个函数接收一个 `UserQuestion`，返回一个 `string`。

参数 `question` 来自 `main()` 里的循环。

里面的 `if` 用来处理真实工程问题：用户名可能为空。

如果用户名为空，就返回：

```text
匿名用户的问题：...
```

这比只做固定字符串拼接更有学习价值，因为它暴露了“空数据处理”。

## `summarizeQuestion()`

这个函数把一个 `UserQuestion` 转成 `QuestionSummary`。

关键点：

- `len(question.Tags)` 计算标签数量。
- `NeedFastAI: question.Urgent` 把是否紧急映射成是否优先交给 AI。
- 返回结构体时使用字段名，代码更清楚。

## `main()`

`main()` 是程序入口。

流程是：

```text
创建 questions slice
-> 打印标题
-> 遍历每个问题
-> 调 summarizeQuestion()
-> 打印摘要和处理建议
```

`for index, question := range questions` 里：

- `index` 是下标，从 0 开始。
- `question` 是当前问题。
- `index+1` 是为了让输出从 1 开始，更符合人的阅读习惯。

## 运行结果应该看什么

运行：

```powershell
go run 01_struct_and_slice.go
```

重点观察：

- 有用户名的问题如何显示。
- 没有用户名的问题如何变成匿名用户。
- `Urgent: true` 的问题如何被标记为优先转发。

## 练习

1. 新增一个 `UserQuestion`，让它没有标签，观察 `TagCount`。
2. 把 `Urgent` 改成 `true`，观察处理建议如何变化。
3. 给 `UserQuestion` 增加 `Source string` 字段，例如 `web` 或 `cli`，并在摘要里显示来源。
4. 修改 `buildTitle()`：如果 `Text` 为空，返回“空问题不能发送给 AI”。

这些练习对应真实开发能力：空数据处理、字段扩展、输入输出结构转换。

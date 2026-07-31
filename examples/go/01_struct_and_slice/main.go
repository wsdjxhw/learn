package main

import "fmt"

// UserQuestion 用来表示“用户准备发给 AI 的一个问题”。
// Go 没有 Java 那种 class 关键字，通常用 struct 表示一组字段。
// 可以先类比成 Java 里的一个简单 POJO / DTO：只负责装数据，不一定带复杂行为。
type UserQuestion struct {
	ID       int
	UserName string
	Text     string
	Tags     []string
	Urgent   bool
}

// QuestionSummary 是整理后的问题摘要。
// 把“原始输入 UserQuestion”和“整理后的输出 QuestionSummary”分开，
// 是为了让初学者先建立 DTO 思维：输入结构和输出结构可以不同。
type QuestionSummary struct {
	ID         int
	Title      string
	TagCount   int
	NeedFastAI bool
}

func buildTitle(question UserQuestion) string {
	// 函数参数 question 从哪里来？
	// 它来自 main() 里的 for 循环，每次循环会拿到一个 UserQuestion。
	// 类比 Java：这里像调用 buildTitle(UserQuestion question)。
	if question.UserName == "" {
		return "匿名用户的问题：" + question.Text
	}

	return question.UserName + " 的问题：" + question.Text
}

func summarizeQuestion(question UserQuestion) QuestionSummary {
	// 返回值是什么？
	// 这里返回 QuestionSummary，而不是直接打印字符串。
	// 这样后续如果要把摘要写入数据库、返回给 API、继续转发给网关，都更方便。
	return QuestionSummary{
		ID:         question.ID,
		Title:      buildTitle(question),
		TagCount:   len(question.Tags),
		NeedFastAI: question.Urgent,
	}
}

func main() {
	// slice 可以先理解成“长度可以变化的数组”，类似 Java 里的 ArrayList。
	// []UserQuestion 表示这个 slice 里的每个元素都是 UserQuestion。
	questions := []UserQuestion{
		{
			ID:       1,
			UserName: "小明",
			Text:     "Go 的 struct 和 Java class 有什么区别？",
			Tags:     []string{"go", "backend"},
			Urgent:   false,
		},
		{
			ID:       2,
			UserName: "",
			Text:     "AI 网关为什么要做统一入口？",
			Tags:     []string{"gateway", "ai"},
			Urgent:   true,
		},
	}

	fmt.Println("准备发送给 AI 服务的问题摘要：")

	// for range 是 Go 最常见的遍历写法。
	// index 是下标，从 0 开始；question 是当前这一项。
	// 如果只需要 question，不需要 index，可以写成：for _, question := range questions
	for index, question := range questions {
		summary := summarizeQuestion(question)

		fmt.Printf("%d. #%d %s\n", index+1, summary.ID, summary.Title)
		fmt.Printf("   标签数量：%d\n", summary.TagCount)

		if summary.NeedFastAI {
			fmt.Println("   处理建议：优先转发给 AI 服务")
		} else {
			fmt.Println("   处理建议：普通队列即可")
		}
	}
}

package main

import "fmt"

// Book 用来演示 Go 里最基础的数据结构：struct。
type Book struct {
	Title  string
	Author string
}

func main() {
	// slice 很像动态数组，后面处理 API 返回结果时会经常用到。
	books := []Book{
		{Title: "Learning Python", Author: "Author A"},
		{Title: "Go Web Basics", Author: "Author B"},
	}

	for index, book := range books {
		fmt.Printf("%d. %s by %s\n", index+1, book.Title, book.Author)
	}
}

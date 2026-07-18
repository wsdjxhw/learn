package main

import (
	"encoding/json"
	"log"
	"net/http"
)

// 统一响应结构，方便前后端按固定格式通信。
type MessageResponse struct {
	Message string `json:"message"`
}

func healthHandler(writer http.ResponseWriter, request *http.Request) {
	writer.Header().Set("Content-Type", "application/json")
	json.NewEncoder(writer).Encode(MessageResponse{Message: "ok"})
}

func helloHandler(writer http.ResponseWriter, request *http.Request) {
	// Query 参数是最简单的入门方式，适合理解 HTTP 请求的输入来源。
	name := request.URL.Query().Get("name")
	if name == "" {
		name = "world"
	}

	writer.Header().Set("Content-Type", "application/json")
	json.NewEncoder(writer).Encode(MessageResponse{Message: "hello, " + name})
}

func main() {
	// 先注册路由，再启动服务，是 Go 原生 HTTP 的基本模式。
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/hello", helloHandler)

	log.Println("server running on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

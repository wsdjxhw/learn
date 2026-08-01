package main

import (
	"log"
	"net/http"
)

func main() {
	// main 是程序入口，职责要尽量简单：
	// 1. 读取配置。
	// 2. 创建需要的组件。
	// 3. 注册路由。
	// 4. 启动 HTTP 服务。
	config := LoadConfig(".env")
	client := NewAIClient(config)
	server := NewServer(config, client)

	mux := http.NewServeMux()
	server.RegisterRoutes(mux)

	address := ":" + config.Port
	log.Printf("go AI gateway running on http://127.0.0.1%s", address)
	log.Printf("mock mode: %v, backend: %s%s", client.shouldUseMock(), config.AIBackendURL, config.AIBackendChatPath)

	if err := http.ListenAndServe(address, loggingMiddleware(mux)); err != nil {
		log.Fatal(err)
	}
}

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
)

// ChatRequest 表示调用方 POST /chat-preview 时传入的 JSON 请求体。
// 类比 Java 里的请求 DTO，也类比 FastAPI 里的 Pydantic BaseModel。
// 注意：Go 字段必须大写开头，encoding/json 才能读写这些字段。
type ChatRequest struct {
	Message string `json:"message"`
}

// ChatPreviewResponse 表示接口返回给调用方的 JSON。
// json tag 控制 JSON 字段名，例如 MessageLength 会变成 message_length。
type ChatPreviewResponse struct {
	Message       string `json:"message"`
	MessageLength int    `json:"message_length"`
	Preview       string `json:"preview"`
}

type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
}

type HelloResponse struct {
	Message string `json:"message"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

func writeJSON(writer http.ResponseWriter, statusCode int, value interface{}) {
	// writer 是 Go 标准库给 handler 的“响应写入器”。
	// 类比 Java Servlet 里的 HttpServletResponse：用它设置响应头、状态码和响应体。
	writer.Header().Set("Content-Type", "application/json")
	writer.WriteHeader(statusCode)

	if err := json.NewEncoder(writer).Encode(value); err != nil {
		// Encode 可能失败，比如连接中断。这里先记录日志，不把复杂错误处理展开。
		log.Printf("encode response failed: %v", err)
	}
}

func writeError(writer http.ResponseWriter, statusCode int, message string) {
	writeJSON(writer, statusCode, ErrorResponse{Error: message})
}

func healthHandler(writer http.ResponseWriter, request *http.Request) {
	// request.Method 来自 HTTP 请求方法。
	// 浏览器直接打开通常是 GET；表单、接口工具或前端代码也可以发 POST。
	if request.Method != http.MethodGet {
		writeError(writer, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	writeJSON(writer, http.StatusOK, HealthResponse{
		Status:  "ok",
		Service: "go-http-basics",
	})
}

func helloHandler(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodGet {
		writeError(writer, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	// Query 参数来自 URL 的 ?name=xxx。
	// 例如 /hello?name=Tom，这里读到的 name 就是 Tom。
	name := strings.TrimSpace(request.URL.Query().Get("name"))
	if name == "" {
		name = "world"
	}

	writeJSON(writer, http.StatusOK, HelloResponse{
		Message: "hello, " + name,
	})
}

func chatPreviewHandler(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodPost {
		writeError(writer, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var payload ChatRequest

	// request.Body 是 HTTP 请求体。
	// json.NewDecoder(...).Decode(&payload) 会把 JSON 字段填进 payload 这个 struct。
	// &payload 里的 & 表示传地址，Go 才能修改 payload 里的字段。
	if err := json.NewDecoder(request.Body).Decode(&payload); err != nil {
		writeError(writer, http.StatusBadRequest, "invalid JSON body")
		return
	}

	message := strings.TrimSpace(payload.Message)
	if message == "" {
		writeError(writer, http.StatusBadRequest, "message must not be empty")
		return
	}

	writeJSON(writer, http.StatusOK, ChatPreviewResponse{
		Message:       message,
		MessageLength: len(message),
		Preview:       fmt.Sprintf("这条消息稍后可以转发给 AI 服务：%s", message),
	})
}

func main() {
	// ServeMux 是 Go 标准库里的路由表。
	// 类比 Spring MVC 的路由注册，或者 FastAPI 里 @app.get("/health") 记录的路径映射。
	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/hello", helloHandler)
	mux.HandleFunc("/chat-preview", chatPreviewHandler)

	address := ":8080"
	log.Println("Go HTTP basics server running on http://127.0.0.1" + address)

	// ListenAndServe 会一直阻塞运行，直到服务出错或被手动停止。
	// log.Fatal 会把错误打印出来并退出程序。
	if err := http.ListenAndServe(address, mux); err != nil {
		log.Fatal(err)
	}
}

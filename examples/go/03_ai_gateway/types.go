package main

// ChatRequest 是前端或调用方传给 Go 网关的请求体。
// 类比 Java 里的请求 DTO：它只描述 HTTP JSON 的形状，不负责真正调用模型。
type ChatRequest struct {
	Message      string `json:"message"`
	SystemPrompt string `json:"system_prompt"`
}

// ChatResponse 是 Go 网关返回给调用方的统一结构。
// source 用来说明结果来自 mock，还是来自 Python AI 后端。
type ChatResponse struct {
	Message  string `json:"message"`
	Reply    string `json:"reply"`
	Provider string `json:"provider"`
	Model    string `json:"model"`
	Source   string `json:"source"`
}

// BackendChatResponse 用来接收 Python AI 服务的 /chat 返回值。
// 这里只保留网关关心的字段；后端返回更多字段时，Go 的 json 解码会自动忽略。
type BackendChatResponse struct {
	Message  string `json:"message"`
	Reply    string `json:"reply"`
	Provider string `json:"provider"`
	Model    string `json:"model"`
}

type HealthResponse struct {
	Status          string `json:"status"`
	Service         string `json:"service"`
	MockMode        bool   `json:"mock_mode"`
	BackendURL      string `json:"backend_url"`
	BackendChatPath string `json:"backend_chat_path"`
	MaxBatchSize    int    `json:"max_batch_size"`
}

type BatchChatRequest struct {
	Messages     []string `json:"messages"`
	SystemPrompt string   `json:"system_prompt"`
}

type BatchChatItem struct {
	Index   int    `json:"index"`
	Message string `json:"message"`
	Reply   string `json:"reply,omitempty"`
	Error   string `json:"error,omitempty"`
	Source  string `json:"source,omitempty"`
}

type BatchChatResponse struct {
	Items []BatchChatItem `json:"items"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

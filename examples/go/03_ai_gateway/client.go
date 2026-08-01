package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// AIClient 负责和 Python AI 服务通信。
// 类比 Java 里的 Service Client / Feign Client：handler 不直接拼 HTTP 请求，避免接口层和外部调用细节混在一起。
type AIClient struct {
	config     Config
	httpClient *http.Client
}

func NewAIClient(config Config) *AIClient {
	return &AIClient{
		config: config,
		httpClient: &http.Client{
			Timeout: config.AIBackendTimeout,
		},
	}
}

func (client *AIClient) GenerateReply(ctx context.Context, payload ChatRequest) (ChatResponse, error) {
	if client.shouldUseMock() {
		return client.generateMockReply(payload), nil
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return ChatResponse{}, fmt.Errorf("encode request: %w", err)
	}

	targetURL := client.config.AIBackendURL + client.config.AIBackendChatPath
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, targetURL, bytes.NewReader(body))
	if err != nil {
		return ChatResponse{}, fmt.Errorf("build backend request: %w", err)
	}
	request.Header.Set("Content-Type", "application/json")

	// 如果后面的 Python 服务启用了 X-API-Key 鉴权，Go 网关可以在这里统一补上。
	// 这样浏览器或上游调用方不需要知道 Python 服务的内部密钥。
	if client.config.AIBackendAPIKey != "" {
		request.Header.Set("X-API-Key", client.config.AIBackendAPIKey)
	}

	response, err := client.httpClient.Do(request)
	if err != nil {
		return ChatResponse{}, fmt.Errorf("call backend: %w", err)
	}
	defer response.Body.Close()

	responseBody, err := io.ReadAll(io.LimitReader(response.Body, 1024*1024))
	if err != nil {
		return ChatResponse{}, fmt.Errorf("read backend response: %w", err)
	}

	if response.StatusCode >= 400 {
		return ChatResponse{}, fmt.Errorf("backend status %d: %s", response.StatusCode, string(responseBody))
	}

	var backend BackendChatResponse
	if err := json.Unmarshal(responseBody, &backend); err != nil {
		return ChatResponse{}, fmt.Errorf("decode backend response: %w", err)
	}

	return ChatResponse{
		Message:  firstNonEmpty(backend.Message, payload.Message),
		Reply:    backend.Reply,
		Provider: firstNonEmpty(backend.Provider, "python-backend"),
		Model:    firstNonEmpty(backend.Model, "unknown"),
		Source:   "python-backend",
	}, nil
}

func (client *AIClient) shouldUseMock() bool {
	// 只要显式开启 mock，或者没有配置后端地址，就不访问外部服务。
	// 这个设计符合本项目原则：没有密钥、没有外部依赖时也能先跑通主流程。
	return client.config.AIBackendMock || client.config.AIBackendURL == ""
}

func (client *AIClient) generateMockReply(payload ChatRequest) ChatResponse {
	message := strings.TrimSpace(payload.Message)
	if message == "" {
		message = "(empty)"
	}

	return ChatResponse{
		Message:  message,
		Reply:    "mock reply from Go gateway: 已收到你的消息，真实项目中这里会转发给 Python AI 服务。",
		Provider: "mock",
		Model:    "go-gateway-mock",
		Source:   "go-mock",
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

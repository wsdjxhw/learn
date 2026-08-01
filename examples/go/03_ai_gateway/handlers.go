package main

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"
)

// Server 把配置和业务客户端组合起来，再提供 HTTP handler。
// 类比 Java Controller 持有 Service：Controller 处理请求参数，Service 处理核心调用。
type Server struct {
	config Config
	client *AIClient
}

func NewServer(config Config, client *AIClient) *Server {
	return &Server{config: config, client: client}
}

func (server *Server) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/health", server.healthHandler)
	mux.HandleFunc("/gateway/chat", server.chatHandler)
	mux.HandleFunc("/gateway/batch-chat", server.batchChatHandler)
}

func (server *Server) healthHandler(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodGet {
		writeError(writer, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	writeJSON(writer, http.StatusOK, HealthResponse{
		Status:          "ok",
		Service:         "go-ai-gateway",
		MockMode:        server.client.shouldUseMock(),
		BackendURL:      server.config.AIBackendURL,
		BackendChatPath: server.config.AIBackendChatPath,
		MaxBatchSize:    server.config.MaxBatchSize,
	})
}

func (server *Server) chatHandler(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodPost {
		writeError(writer, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var payload ChatRequest
	if err := json.NewDecoder(request.Body).Decode(&payload); err != nil {
		writeError(writer, http.StatusBadRequest, "invalid JSON body")
		return
	}

	payload.Message = strings.TrimSpace(payload.Message)
	if payload.Message == "" {
		writeError(writer, http.StatusBadRequest, "message must not be empty")
		return
	}
	if strings.TrimSpace(payload.SystemPrompt) == "" {
		payload.SystemPrompt = "You are a helpful assistant."
	}

	reply, err := server.client.GenerateReply(request.Context(), payload)
	if err != nil {
		writeError(writer, http.StatusBadGateway, err.Error())
		return
	}

	writeJSON(writer, http.StatusOK, reply)
}

func (server *Server) batchChatHandler(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodPost {
		writeError(writer, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var payload BatchChatRequest
	if err := json.NewDecoder(request.Body).Decode(&payload); err != nil {
		writeError(writer, http.StatusBadRequest, "invalid JSON body")
		return
	}

	if len(payload.Messages) == 0 {
		writeError(writer, http.StatusBadRequest, "messages must not be empty")
		return
	}
	if len(payload.Messages) > server.config.MaxBatchSize {
		writeError(writer, http.StatusBadRequest, "too many messages")
		return
	}
	if strings.TrimSpace(payload.SystemPrompt) == "" {
		payload.SystemPrompt = "You are a helpful assistant."
	}

	items := make([]BatchChatItem, len(payload.Messages))
	var waitGroup sync.WaitGroup

	for index, message := range payload.Messages {
		index := index
		message := strings.TrimSpace(message)
		items[index] = BatchChatItem{Index: index, Message: message}

		if message == "" {
			items[index].Error = "message must not be empty"
			continue
		}

		waitGroup.Add(1)
		go func() {
			defer waitGroup.Done()

			// goroutine 类似轻量线程，适合并发等待多个后端调用返回。
			// 注意这里每个 goroutine 只写自己的 items[index]，避免多个 goroutine 抢同一个位置。
			reply, err := server.client.GenerateReply(request.Context(), ChatRequest{
				Message:      message,
				SystemPrompt: payload.SystemPrompt,
			})
			if err != nil {
				items[index].Error = err.Error()
				return
			}

			items[index].Reply = reply.Reply
			items[index].Source = reply.Source
		}()
	}

	waitGroup.Wait()
	writeJSON(writer, http.StatusOK, BatchChatResponse{Items: items})
}

func writeJSON(writer http.ResponseWriter, statusCode int, payload any) {
	writer.Header().Set("Content-Type", "application/json")
	writer.WriteHeader(statusCode)
	if err := json.NewEncoder(writer).Encode(payload); err != nil {
		log.Printf("encode response failed: %v", err)
	}
}

func writeError(writer http.ResponseWriter, statusCode int, message string) {
	writeJSON(writer, statusCode, ErrorResponse{Error: message})
}

type statusWriter struct {
	http.ResponseWriter
	statusCode int
}

func (writer *statusWriter) WriteHeader(statusCode int) {
	writer.statusCode = statusCode
	writer.ResponseWriter.WriteHeader(statusCode)
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		startedAt := time.Now()
		wrapped := &statusWriter{ResponseWriter: writer, statusCode: http.StatusOK}

		next.ServeHTTP(wrapped, request)

		log.Printf(
			"%s %s -> %d (%s)",
			request.Method,
			request.URL.Path,
			wrapped.statusCode,
			time.Since(startedAt).Round(time.Millisecond),
		)
	})
}

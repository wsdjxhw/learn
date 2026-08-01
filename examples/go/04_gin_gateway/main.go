package main

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// ChatPreviewRequest 表示调用方 POST /api/chat-preview 时传入的 JSON 请求体。
// 类比 Java 里的请求 DTO，也类比 FastAPI 里的 Pydantic BaseModel。
// `json:"message"` 说明 JSON 字段名叫 message。
// `binding:"required"` 是 Gin 的校验标记：请求体里必须提供这个字段。
type ChatPreviewRequest struct {
	Message string `json:"message" binding:"required"`
}

// ChatPreviewResponse 是接口返回给调用方的 JSON 结构。
// 不直接返回散乱的 map，是为了让初学者看到“输入 DTO”和“输出 DTO”可以分开设计。
type ChatPreviewResponse struct {
	Message       string `json:"message"`
	MessageLength int    `json:"message_length"`
	Preview       string `json:"preview"`
	RequestID     string `json:"request_id"`
}

type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
	Mode    string `json:"mode"`
}

type HelloResponse struct {
	Message   string `json:"message"`
	RequestID string `json:"request_id"`
}

type MessageDetailResponse struct {
	MessageID string `json:"message_id"`
	Source    string `json:"source"`
}

type ErrorResponse struct {
	Error     string `json:"error"`
	RequestID string `json:"request_id,omitempty"`
}

func main() {
	router := setupRouter()

	// router.Run(":8081") 会启动 HTTP 服务。
	// 这里固定用 8081，避免和 02_http_server.go 的 8080 冲突。
	if err := router.Run(":8081"); err != nil {
		panic(err)
	}
}

func setupRouter() *gin.Engine {
	// gin.Default() 会创建一个带默认中间件的路由器。
	// 默认中间件包括请求日志 Logger 和崩溃恢复 Recovery。
	// 类比 Java Spring Boot：框架已经帮你准备了基础 Web 运行环境。
	router := gin.Default()

	// Use 注册全局 middleware。
	// 所有请求进入 handler 前，都会先经过 requestIDMiddleware。
	router.Use(requestIDMiddleware())

	// Group 用来给一组接口加统一前缀。
	// 这里所有业务接口都放在 /api 下，后续扩展网关接口时更清楚。
	api := router.Group("/api")
	{
		api.GET("/health", healthHandler)
		api.GET("/hello", helloHandler)
		api.GET("/messages/:message_id", messageDetailHandler)
		api.POST("/chat-preview", chatPreviewHandler)
	}

	return router
}

func requestIDMiddleware() gin.HandlerFunc {
	return func(context *gin.Context) {
		// middleware 可以理解成 Java Web 里的 Filter。
		// 它不是具体业务接口，但每个请求都会经过这里。
		requestID := fmt.Sprintf("req-%d", time.Now().UnixNano())

		// context.Set 把数据放进当前请求上下文。
		// 后面的 handler 可以用 context.GetString("request_id") 取出来。
		context.Set("request_id", requestID)

		// c.Next() 表示继续执行后面的 handler。
		// 如果这里不调用 Next，也不手动返回响应，请求就不会进入真正的接口函数。
		context.Next()
	}
}

func healthHandler(context *gin.Context) {
	// Gin 会根据注册路由时的 GET 自动限制请求方法。
	// 所以这里不用像 net/http 示例那样手写 request.Method 判断。
	context.JSON(http.StatusOK, HealthResponse{
		Status:  "ok",
		Service: "gin-gateway-basics",
		Mode:    gin.Mode(),
	})
}

func helloHandler(context *gin.Context) {
	// Query 参数来自 URL 的 ?name=xxx。
	// Gin 的 DefaultQuery 可以在参数为空时给默认值，比手写 if 更短。
	name := strings.TrimSpace(context.DefaultQuery("name", "world"))
	if name == "" {
		name = "world"
	}

	context.JSON(http.StatusOK, HelloResponse{
		Message:   "hello, " + name,
		RequestID: context.GetString("request_id"),
	})
}

func messageDetailHandler(context *gin.Context) {
	// Path 参数来自路由里的 :message_id。
	// 例如 GET /api/messages/101，context.Param("message_id") 就是 101。
	messageID := strings.TrimSpace(context.Param("message_id"))
	if messageID == "" {
		writeError(context, http.StatusBadRequest, "message_id must not be empty")
		return
	}

	context.JSON(http.StatusOK, MessageDetailResponse{
		MessageID: messageID,
		Source:    "path parameter",
	})
}

func chatPreviewHandler(context *gin.Context) {
	var payload ChatPreviewRequest

	// ShouldBindJSON 会把请求体 JSON 解析到 payload 这个 struct。
	// 和 Gin 的 BindJSON 相比，ShouldBindJSON 只返回错误，不会自动写响应。
	// 这样我们可以统一返回 ErrorResponse，前端更容易处理。
	if err := context.ShouldBindJSON(&payload); err != nil {
		writeError(context, http.StatusBadRequest, "invalid JSON body: message is required")
		return
	}

	message := strings.TrimSpace(payload.Message)
	if message == "" {
		// binding:"required" 能检查字段是否存在，但用户传 "   " 这种全空格字符串时，
		// 仍然需要业务代码自己 trim 后再判断。
		writeError(context, http.StatusBadRequest, "message must not be empty")
		return
	}

	context.JSON(http.StatusOK, ChatPreviewResponse{
		Message:       message,
		MessageLength: len(message),
		Preview:       "Gin 已收到消息，后续网关模块可以把它转发给 Python AI 服务。",
		RequestID:     context.GetString("request_id"),
	})
}

func writeError(context *gin.Context, statusCode int, message string) {
	context.JSON(statusCode, ErrorResponse{
		Error:     message,
		RequestID: context.GetString("request_id"),
	})
}

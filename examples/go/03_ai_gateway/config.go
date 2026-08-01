package main

import (
	"bufio"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config 集中保存网关启动时需要的配置。
// 类比 Java 里的 application.properties + Configuration Bean：
// 代码里不要到处散落 os.Getenv("xxx")，而是先统一读配置，再把配置传给需要的组件。
type Config struct {
	Port              string
	AIBackendURL      string
	AIBackendChatPath string
	AIBackendAPIKey   string
	AIBackendMock     bool
	AIBackendTimeout  time.Duration
	MaxBatchSize      int
}

// LoadConfig 负责读取 .env 和系统环境变量。
// Go 标准库没有内置 dotenv 功能；为了避免初学阶段引入第三方库，这里手写一个很小的解析器。
func LoadConfig(envFile string) Config {
	fileValues := readDotEnvFile(envFile)

	return Config{
		Port:              getString(fileValues, "GO_GATEWAY_PORT", "8081"),
		AIBackendURL:      strings.TrimRight(getString(fileValues, "AI_BACKEND_URL", ""), "/"),
		AIBackendChatPath: ensureLeadingSlash(getString(fileValues, "AI_BACKEND_CHAT_PATH", "/chat")),
		AIBackendAPIKey:   getString(fileValues, "AI_BACKEND_API_KEY", ""),
		AIBackendMock:     getBool(fileValues, "AI_BACKEND_MOCK", true),
		AIBackendTimeout:  time.Duration(getInt(fileValues, "AI_BACKEND_TIMEOUT_SECONDS", 10)) * time.Second,
		MaxBatchSize:      getInt(fileValues, "MAX_BATCH_SIZE", 5),
	}
}

func readDotEnvFile(path string) map[string]string {
	values := map[string]string{}

	file, err := os.Open(path)
	if err != nil {
		// .env 不存在不是错误，因为学习时可以直接使用默认 mock 配置。
		return values
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}

		key := strings.TrimSpace(parts[0])
		value := strings.Trim(strings.TrimSpace(parts[1]), `"'`)
		values[key] = value
	}

	return values
}

func getString(fileValues map[string]string, key string, fallback string) string {
	// 系统环境变量优先级高于 .env，方便部署时由 Docker 或服务器注入配置。
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	if value := strings.TrimSpace(fileValues[key]); value != "" {
		return value
	}
	return fallback
}

func getBool(fileValues map[string]string, key string, fallback bool) bool {
	raw := strings.ToLower(getString(fileValues, key, ""))
	if raw == "" {
		return fallback
	}
	return raw == "true" || raw == "1" || raw == "yes"
}

func getInt(fileValues map[string]string, key string, fallback int) int {
	raw := getString(fileValues, key, "")
	if raw == "" {
		return fallback
	}

	value, err := strconv.Atoi(raw)
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}

func ensureLeadingSlash(path string) string {
	if strings.HasPrefix(path, "/") {
		return path
	}
	return "/" + path
}

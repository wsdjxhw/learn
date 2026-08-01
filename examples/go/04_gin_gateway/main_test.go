package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestHealth(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := setupRouter()

	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/health", nil)

	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", response.Code)
	}
}

func TestChatPreviewRejectsEmptyMessage(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := setupRouter()

	body := bytes.NewBufferString(`{"message":"   "}`)
	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/chat-preview", body)
	request.Header.Set("Content-Type", "application/json")

	router.ServeHTTP(response, request)

	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", response.Code)
	}
}

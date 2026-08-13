package engine

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func testClient(srv *httptest.Server) *Client {
	return &Client{base: srv.URL, hc: srv.Client()}
}

func TestWaitReady(t *testing.T) {
	var calls int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			t.Errorf("path = %q, want /health", r.URL.Path)
		}
		calls++
		if calls < 3 {
			w.WriteHeader(http.StatusServiceUnavailable) // model still loading
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	if err := testClient(srv).WaitReady(10 * time.Second); err != nil {
		t.Fatalf("WaitReady: %v", err)
	}
	if calls < 3 {
		t.Errorf("health polled %d times, want at least 3", calls)
	}
}

func TestWaitReadyTimeout(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	if err := testClient(srv).WaitReady(0); err == nil {
		t.Fatal("expected timeout error, got nil")
	}
}

func TestComplete(t *testing.T) {
	var got completionReq
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/completion" {
			t.Errorf("path = %q, want /completion", r.URL.Path)
		}
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Errorf("request body did not decode: %v", err)
		}
		w.Write([]byte(`{"content":"  find . -size +100M \n"}`))
	}))
	defer srv.Close()

	cmd, err := testClient(srv).Complete("cari file lagi besar dari 100MB")
	if err != nil {
		t.Fatalf("Complete: %v", err)
	}
	if cmd != "find . -size +100M" {
		t.Errorf("cmd = %q, want trimmed command", cmd)
	}

	// The fixed decoding contract: temp 0, 64 tokens, grammar.
	if got.Temperature != 0 {
		t.Errorf("temperature = %v, want 0", got.Temperature)
	}
	if got.NPredict != 64 {
		t.Errorf("n_predict = %d, want 64", got.NPredict)
	}
	if got.Grammar != grammar || got.Grammar == "" {
		t.Errorf("grammar = %q, want %q", got.Grammar, grammar)
	}
	if len(got.Stop) == 0 || got.Stop[0] != "\n" {
		t.Errorf("stop = %q, want [\"\\n\"]", got.Stop)
	}
	// The ChatML template the model was trained on, with the query inside.
	if !strings.Contains(got.Prompt, "<|im_start|>system\n"+systemPrompt+"<|im_end|>") {
		t.Errorf("prompt missing system message: %q", got.Prompt)
	}
	if !strings.Contains(got.Prompt, "<|im_start|>user\ncari file lagi besar dari 100MB<|im_end|>") {
		t.Errorf("prompt missing user message: %q", got.Prompt)
	}
	if !strings.HasSuffix(got.Prompt, "<|im_start|>assistant\n") {
		t.Errorf("prompt must end at the assistant turn: %q", got.Prompt)
	}
}

func TestCompleteStripsUnprintable(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// A hostile server answering with control bytes: ESC, BEL, NUL.
		w.Write([]byte(`{"content":"ls\u0000 -la\u0007\u001b"}`))
	}))
	defer srv.Close()

	cmd, err := testClient(srv).Complete("senaraikan file")
	if err != nil {
		t.Fatalf("Complete: %v", err)
	}
	if cmd != "ls -la" {
		t.Errorf("cmd = %q, want control bytes stripped", cmd)
	}
}

func TestCompleteEmptyAnswer(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"content":"  \u0007 "}`))
	}))
	defer srv.Close()

	if _, err := testClient(srv).Complete("apa-apa"); err == nil {
		t.Fatal("expected error for empty answer, got nil")
	}
}

func TestCompleteServerError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	if _, err := testClient(srv).Complete("apa-apa"); err == nil {
		t.Fatal("expected error on HTTP 500, got nil")
	}
}

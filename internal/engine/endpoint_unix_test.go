//go:build !windows

package engine

import (
	"net"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

// The unix-socket transport must reach an HTTP server listening on the
// socket file — this is the wiring a TCP httptest server cannot cover.
func TestUnixTransport(t *testing.T) {
	sock := filepath.Join(t.TempDir(), "llama.sock")
	l, err := net.Listen("unix", sock)
	if err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	srv.Listener = l
	srv.Start()
	defer srv.Close()

	ready, alive := unixClient(sock).health()
	if !ready || !alive {
		t.Fatalf("health over unix socket = (ready=%v, alive=%v), want both true", ready, alive)
	}
}

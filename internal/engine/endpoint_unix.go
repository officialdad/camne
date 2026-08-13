//go:build !windows

package engine

import (
	"context"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"syscall"
)

// The socket lives in the 0700 run dir, so filesystem permissions gate access
// — unlike a loopback port, which every UID on a shared box can reach, and
// which another process could squat between restarts.
// llama-server binds a UNIX socket when --host ends in ".sock", verified in
// common/arg.cpp at the pinned b10333 tag.

func sockPath(rd string) string { return filepath.Join(rd, "llama.sock") }

func unixClient(sock string) *Client {
	return &Client{
		base: "http://camne", // placeholder host; the dialer ignores it
		hc: &http.Client{Transport: &http.Transport{
			DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
				var d net.Dialer
				return d.DialContext(ctx, "unix", sock)
			},
		}},
	}
}

// newEndpoint picks the transport for a fresh server: the client to reach it
// and the --host arguments llama-server needs to serve there.
func newEndpoint(rd string) (*Client, []string, error) {
	s := sockPath(rd)
	return unixClient(s), []string{"--host", s}, nil
}

// existingClient returns a client for a possibly-running server, or nil when
// there is clearly none.
func existingClient(rd string) *Client {
	s := sockPath(rd)
	if _, err := os.Stat(s); err != nil {
		return nil
	}
	return unixClient(s)
}

func cleanRunFiles(rd string) {
	os.Remove(sockPath(rd))
	os.Remove(pidPath(rd))
}

// detachAttr makes llama-server its own session leader, so it survives the
// camne process and its terminal going away.
func detachAttr() *syscall.SysProcAttr { return &syscall.SysProcAttr{Setsid: true} }

func terminate(pid int) error { return syscall.Kill(pid, syscall.SIGTERM) }

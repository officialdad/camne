package engine

import (
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

// Windows difference: llama-server's ".sock"
// binding is a POSIX path convention, so camne falls back to a loopback TCP
// port here. Two consequences vs the unix-socket transport: loopback is
// reachable by every local user, and the port is picked by binding :0 then
// releasing it for llama-server, which leaves a window where another process
// could squat it. Both are tolerated because camne never executes what comes
// back — every response is control-byte-filtered, safety-checked and printed,
// nothing more.

func portPath(rd string) string { return filepath.Join(rd, "llama.port") }

func tcpClient(port string) *Client {
	return &Client{base: "http://127.0.0.1:" + port, hc: &http.Client{}}
}

func newEndpoint(rd string) (*Client, []string, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, nil, errors.New("tak boleh buka port tempatan untuk llama-server — cuba lagi")
	}
	port := strconv.Itoa(l.Addr().(*net.TCPAddr).Port)
	l.Close()
	if err := os.WriteFile(portPath(rd), []byte(port), 0o600); err != nil {
		return nil, nil, fmt.Errorf("tak boleh simpan fail port: %w", err)
	}
	return tcpClient(port), []string{"--host", "127.0.0.1", "--port", port}, nil
}

func existingClient(rd string) *Client {
	b, err := os.ReadFile(portPath(rd))
	if err != nil {
		return nil
	}
	return tcpClient(strings.TrimSpace(string(b)))
}

func cleanRunFiles(rd string) {
	os.Remove(portPath(rd))
	os.Remove(pidPath(rd))
}

// DETACHED_PROCESS is not in the syscall package.
const detachedProcess = 0x00000008

// detachAttr detaches llama-server from camne's console so it survives the
// camne process (and its console window) going away.
func detachAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP | detachedProcess,
		HideWindow:    true,
	}
}

func terminate(pid int) error {
	p, err := os.FindProcess(pid)
	if err != nil {
		return err
	}
	return p.Kill()
}

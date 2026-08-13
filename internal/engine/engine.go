// Package engine drives a resident llama-server (PROMPT.md §4.2). The first
// query starts the server detached and leaves it resident, so later queries
// skip the ~1 GB model load; `camne stop` shuts it down. Transport is a UNIX
// domain socket in a 0700 run directory on linux/darwin (llama-server binds a
// socket when --host ends in ".sock" — verified in common/arg.cpp at the
// pinned b10333 tag). Windows falls back to a loopback TCP port; see
// endpoint_windows.go for the documented difference.
//
// Nothing in this package executes a generated command. It only asks the
// model and returns text.
package engine

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/officialdad/camne/internal/provision"
)

// systemPrompt is the ChatML system message the nl2sh-1.5b model was trained
// with (its model card and whatisit's config.SYSTEM_PROMPT, verbatim).
const systemPrompt = "You are a shell command generator. Output exactly one line: a single POSIX/bash command that accomplishes the user's request. No prose, no markdown fences, no explanation."

// grammar constrains generation to one non-empty line of printable ASCII —
// no newlines, no markdown fences, no "Sure, here's the command:" framing to
// strip afterwards (PROMPT.md §4.2).
const grammar = "root ::= [ -~]+"

// idleSleep: after 30 min idle llama-server unloads the model from RAM; the
// (now tiny) process stays and transparently reloads on the next query.
// --sleep-idle-seconds verified present in the pinned b10333 arg parser.
// `camne stop` kills the process outright.
const idleSleep = "1800"

// Client talks HTTP to one llama-server.
type Client struct {
	base string // URL prefix; a placeholder host when dialing a unix socket
	hc   *http.Client
}

// runDir is the 0700 directory holding the socket, pidfile and server log.
func runDir() (string, error) {
	d, err := provision.Dir()
	if err != nil {
		return "", err
	}
	rd := filepath.Join(d, "run")
	if err := os.MkdirAll(rd, 0o700); err != nil {
		return "", fmt.Errorf("tak boleh buat folder run camne: %w", err)
	}
	if runtime.GOOS != "windows" {
		// MkdirAll leaves a pre-existing dir's mode alone: enforce it anyway,
		// the socket's only access control is this directory's permissions.
		os.Chmod(rd, 0o700)
	}
	return rd, nil
}

func pidPath(rd string) string { return filepath.Join(rd, "llama.pid") }

// threads: decoding is memory-bandwidth-bound, not compute-bound, so half the
// cores capped at 4 is the whatisit-validated default for the target box.
func threads() string {
	n := runtime.NumCPU() / 2
	if n < 1 {
		n = 1
	}
	if n > 4 {
		n = 4
	}
	return strconv.Itoa(n)
}

// Connect returns a client for the resident llama-server, starting one
// detached if nothing is listening. cold reports that the model is not loaded
// yet, so the caller can tell the user why the first answer takes longer.
func Connect(serverPath, modelPath string) (c *Client, cold bool, err error) {
	rd, err := runDir()
	if err != nil {
		return nil, false, err
	}
	if c := existingClient(rd); c != nil {
		if ready, alive := c.health(); alive {
			return c, !ready, nil
		}
	}
	// Nothing answering: clear stale run files and start fresh.
	cleanRunFiles(rd)
	c, hostArgs, err := newEndpoint(rd)
	if err != nil {
		return nil, false, err
	}
	args := append([]string{
		"-m", modelPath,
		"-t", threads(),
		"-c", "2048",
		"--no-webui",
		"--sleep-idle-seconds", idleSleep,
	}, hostArgs...)
	cmd := exec.Command(serverPath, args...)
	// llama-server chatter goes to a log file, never to the user's terminal.
	if logf, lerr := os.OpenFile(filepath.Join(rd, "llama.log"),
		os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600); lerr == nil {
		cmd.Stdout, cmd.Stderr = logf, logf
		defer logf.Close()
	}
	cmd.SysProcAttr = detachAttr()
	if err := cmd.Start(); err != nil {
		return nil, false, fmt.Errorf("tak boleh start llama-server — jalankan `camne doctor` untuk semak: %w", err)
	}
	os.WriteFile(pidPath(rd), []byte(strconv.Itoa(cmd.Process.Pid)), 0o600)
	cmd.Process.Release()
	return c, true, nil
}

// health reports (ready, alive): ready means HTTP 200; alive means the server
// answered at all (it returns 503 while the model is still loading).
func (c *Client) health() (ready, alive bool) {
	ctx, cancel := context.WithTimeout(context.Background(), 700*time.Millisecond)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.base+"/health", nil)
	if err != nil {
		return false, false
	}
	resp, err := c.hc.Do(req)
	if err != nil {
		return false, false
	}
	resp.Body.Close()
	return resp.StatusCode == http.StatusOK, true
}

// WaitReady polls /health until the model is loaded or the deadline passes.
func (c *Client) WaitReady(timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		if ready, _ := c.health(); ready {
			return nil
		}
		if time.Now().After(deadline) {
			return errors.New("model masih tak sedia — cuba `camne stop`, lepas tu tanya semula. Kalau masih gagal, `camne doctor` boleh tolong semak")
		}
		time.Sleep(300 * time.Millisecond)
	}
}

type completionReq struct {
	Prompt      string   `json:"prompt"`
	NPredict    int      `json:"n_predict"`
	Temperature float64  `json:"temperature"`
	Grammar     string   `json:"grammar"`
	Stop        []string `json:"stop"`
	CachePrompt bool     `json:"cache_prompt"`
	// Greedy decoding on nl2sh-1.5b degenerates without a small repetition
	// penalty — whatisit documented flag spam ("zip -r -9 -q -n -j -0 ..."),
	// and we reproduced `: > file.txt` instead of `touch file.txt` on
	// colloquial BM input. 1.08/64 matches whatisit's measured settings;
	// dropping them during the Go port was a regression.
	RepeatPenalty float64 `json:"repeat_penalty"`
	RepeatLastN   int     `json:"repeat_last_n"`
}

// chatML wraps the question in the ChatML template the nl2sh-1.5b model (a
// Qwen2.5-Coder-1.5B-Instruct fine-tune) expects, per its model card.
func chatML(query string) string {
	return "<|im_start|>system\n" + systemPrompt + "<|im_end|>\n" +
		"<|im_start|>user\n" + query + "<|im_end|>\n" +
		"<|im_start|>assistant\n"
}

// Complete asks the model for one command. Decoding is fixed — temperature 0,
// 64 tokens max, grammar-constrained to a single line — the same settings
// every benchmark states (PROMPT.md §7.1), so the tool must match them.
func (c *Client) Complete(query string) (string, error) {
	body, err := json.Marshal(completionReq{
		Prompt:        chatML(query),
		NPredict:      64,
		Temperature:   0,
		Grammar:       grammar,
		Stop:          []string{"\n"},
		CachePrompt:   true,
		RepeatPenalty: 1.08,
		RepeatLastN:   64,
	})
	if err != nil {
		return "", fmt.Errorf("soalan tu tak boleh diproses: %w", err)
	}
	// Generous cap: a server that idled to sleep reloads the model first.
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.base+"/completion", bytes.NewReader(body))
	if err != nil {
		return "", errors.New("tak dapat hubungi model — cuba `camne stop`, lepas tu tanya semula")
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.hc.Do(req)
	if err != nil {
		return "", errors.New("tak dapat hubungi model — cuba `camne stop`, lepas tu tanya semula")
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("model bagi ralat (HTTP %d) — cuba `camne stop`, lepas tu tanya semula", resp.StatusCode)
	}
	var out struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", errors.New("jawapan model tak boleh dibaca — cuba tanya semula")
	}
	cmd := strings.TrimSpace(printable(out.Content))
	if cmd == "" {
		return "", errors.New("model tak bagi jawapan kali ni — cuba ubah ayat soalan tu sikit")
	}
	return cmd, nil
}

// printable drops every byte outside the grammar's [ -~] range. The grammar
// already forbids them server-side; this re-check is the trust boundary for a
// response that did not come from our server (e.g. a squatted TCP port on
// Windows) — no control byte may reach the terminal.
func printable(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] >= 0x20 && s[i] <= 0x7e {
			b.WriteByte(s[i])
		}
	}
	return b.String()
}

// Stop shuts the resident server down and removes the run files. It reports
// false when no server was recorded as running.
func Stop() (bool, error) {
	rd, err := runDir()
	if err != nil {
		return false, err
	}
	b, err := os.ReadFile(pidPath(rd))
	if err != nil {
		return false, nil
	}
	stopped := false
	if pid, err := strconv.Atoi(strings.TrimSpace(string(b))); err == nil {
		stopped = terminate(pid) == nil
	}
	cleanRunFiles(rd)
	return stopped, nil
}

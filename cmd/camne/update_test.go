package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// latestTag talks to httptest, never to GitHub: the test suite must not need a
// network, and a rate-limited API would make it flaky.
func TestLatestTag(t *testing.T) {
	for _, tt := range []struct {
		name   string
		status int
		body   string
		want   string
	}{
		{"a normal release", 200, `{"tag_name":"v0.4.0","name":"camne 0.4.0"}`, "v0.4.0"},
		{"fields camne does not care about", 200, `{"assets":[{"name":"camne_linux_amd64"}],"tag_name":"v1.2.3"}`, "v1.2.3"},
		{"malformed body", 200, `{"tag_name": `, ""},
		{"not JSON at all", 200, `<html>502 Bad Gateway</html>`, ""},
		{"empty body", 200, ``, ""},
		{"no tag in the reply", 200, `{"name":"camne"}`, ""},
		{"rate limited", 403, `{"message":"API rate limit exceeded"}`, ""},
		{"nothing released yet", 404, `{"message":"Not Found"}`, ""},
	} {
		t.Run(tt.name, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(tt.status)
				w.Write([]byte(tt.body))
			}))
			defer srv.Close()
			got, err := latestTag(srv.URL)
			if got != tt.want {
				t.Errorf("latestTag() = %q, want %q", got, tt.want)
			}
			if (err != nil) != (tt.want == "") {
				t.Errorf("latestTag() err = %v, want error: %v", err, tt.want == "")
			}
		})
	}
}

// An unreachable server must be an error, not a hang and not a crash.
func TestLatestTagUnreachable(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	url := srv.URL
	srv.Close()
	if _, err := latestTag(url); err == nil {
		t.Error("latestTag() on a closed server = nil error, want an error")
	}
}

const checksums = `936ce04d98abe2a977e9dd2ff92659bb96947e136acee8f2bc3e21d8eaebbf23  camne_linux_amd64
95da1a0f7538340f625b0301593ee63c046ec0a155c74f21444ea4d43bca79a1  camne_linux_arm64
6ffd9e0b9b2e3ab6ccfba332a74b968b0fef891f01bd4747d3d75bc7393877ea *camne_windows_amd64.exe
`

func TestSumFor(t *testing.T) {
	for _, tt := range []struct {
		name  string
		asset string
		want  string
	}{
		{"present", "camne_linux_amd64", "936ce04d98abe2a977e9dd2ff92659bb96947e136acee8f2bc3e21d8eaebbf23"},
		{"a later line", "camne_linux_arm64", "95da1a0f7538340f625b0301593ee63c046ec0a155c74f21444ea4d43bca79a1"},
		{"binary-mode asterisk", "camne_windows_amd64.exe", "6ffd9e0b9b2e3ab6ccfba332a74b968b0fef891f01bd4747d3d75bc7393877ea"},
		{"arch not in this release", "camne_freebsd_riscv64", ""},
		{"a prefix of a real name matches nothing", "camne_linux_amd", ""},
	} {
		t.Run(tt.name, func(t *testing.T) {
			got, err := sumFor(checksums, tt.asset)
			if got != tt.want {
				t.Errorf("sumFor(%q) = %q, want %q", tt.asset, got, tt.want)
			}
			if (err != nil) != (tt.want == "") {
				t.Errorf("sumFor(%q) err = %v, want error: %v", tt.asset, err, tt.want == "")
			}
		})
	}
	if _, err := sumFor("", "camne_linux_amd64"); err == nil {
		t.Error("sumFor on an empty listing = nil error, want an error — an unverifiable download must never proceed")
	}
}

// These names are also what scripts/build.sh writes and what install.sh greps
// for. If this test changes, those two change with it.
func TestAssetName(t *testing.T) {
	for _, tt := range []struct{ goos, goarch, want string }{
		{"linux", "amd64", "camne_linux_amd64"},
		{"linux", "arm64", "camne_linux_arm64"},
		{"darwin", "amd64", "camne_darwin_amd64"},
		{"darwin", "arm64", "camne_darwin_arm64"},
		{"windows", "amd64", "camne_windows_amd64.exe"},
		{"windows", "arm64", "camne_windows_arm64.exe"},
	} {
		if got := assetName(tt.goos, tt.goarch); got != tt.want {
			t.Errorf("assetName(%q, %q) = %q, want %q", tt.goos, tt.goarch, got, tt.want)
		}
	}
}

func TestShouldCheck(t *testing.T) {
	now := time.Date(2026, 8, 14, 12, 0, 0, 0, time.UTC)
	dir := t.TempDir()

	fresh := filepath.Join(dir, "fresh")
	touch(fresh)
	os.Chtimes(fresh, now.Add(-time.Hour), now.Add(-time.Hour))

	stale := filepath.Join(dir, "stale")
	touch(stale)
	os.Chtimes(stale, now.Add(-25*time.Hour), now.Add(-25*time.Hour))

	missing := filepath.Join(dir, "never-checked")

	for _, tt := range []struct {
		name  string
		ver   string
		stamp string
		tty   bool
		want  bool
	}{
		{"released binary, never checked, on a terminal", "v0.3.1", missing, true, true},
		{"released binary, last check 25 h ago", "v0.3.1", stale, true, true},
		{"last check 1 h ago", "v0.3.1", fresh, true, false},
		{"locally built binary", "dev", missing, true, false},
		{"piped, so no prompt is possible", "v0.3.1", missing, false, false},
		{"piped and stale", "v0.3.1", stale, false, false},
	} {
		t.Run(tt.name, func(t *testing.T) {
			if got := shouldCheck(tt.ver, tt.stamp, tt.tty, now); got != tt.want {
				t.Errorf("shouldCheck(%q, tty=%v) = %v, want %v", tt.ver, tt.tty, got, tt.want)
			}
		})
	}

	// touch on an existing stamp has to move the mtime forward, or the
	// throttle would only ever work once. These two assertions measure a real
	// mtime, so they take their reference from the real clock — pairing the
	// frozen `now` above with a real touch made this test expire on
	// 2026-08-15, when now+48h stopped being 24 h clear of time.Now().
	touch(fresh)
	if !shouldCheck("v0.3.1", fresh, true, time.Now().Add(48*time.Hour)) {
		t.Error("shouldCheck 48 h after a touch = false, want true")
	}
	if shouldCheck("v0.3.1", fresh, true, time.Now()) {
		t.Error("shouldCheck right after a touch = true, want false — the throttle did not record the check")
	}
}

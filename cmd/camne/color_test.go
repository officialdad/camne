package main

import (
	"bytes"
	"os"
	"regexp"
	"strings"
	"testing"
)

var escapeRe = regexp.MustCompile("\x1b\\[[0-9;]*m")

func strip(s string) string { return escapeRe.ReplaceAllString(s, "") }

// The command is what the user pastes into a shell. Colouring it may not move,
// requote or normalize a single byte.
func TestHighlightKeepsEveryByte(t *testing.T) {
	cmds := []string{
		"",
		"ls",
		"ls -lah",
		"   ruang    di    tepi   ",
		"find . -size +100M -exec ls -lh {} \\;",
		"rm -rf '/'",
		`grep -r "hello world" /etc/hosts | wc -l`,
		"tar -czf backup.tar.gz ~/Documents && echo 'siap'",
		`awk '{print $1}' file.txt > out.txt 2>&1`,
		"docker exec -it <container-id> sh",
		`echo "tak ditutup`,
		`echo 'a'"b"c`,
		"cat a.txt;cat b.txt|sort",
	}
	for _, cmd := range cmds {
		if got := strip(highlight(cmd)); got != cmd {
			t.Errorf("highlight(%q) stripped = %q, want the input back byte for byte", cmd, got)
		}
	}
}

func TestHighlightActuallyColours(t *testing.T) {
	got := highlight("ls -lah /etc")
	if !strings.Contains(got, cBinary) || !strings.Contains(got, cFlag) || !strings.Contains(got, cPath) {
		t.Errorf("highlight(%q) = %q, want the binary, flag and path coloured", "ls -lah /etc", got)
	}
}

func TestEnabled(t *testing.T) {
	if enabled(&bytes.Buffer{}) {
		t.Error("enabled(buffer) = true, want false — piped output must stay plain")
	}
	// os.DevNull is a character device, which is as close to a terminal as a
	// test gets without allocating a pty.
	dev, err := os.Open(os.DevNull)
	if err != nil {
		t.Skipf("cannot open %s: %v", os.DevNull, err)
	}
	defer dev.Close()
	if fi, err := dev.Stat(); err != nil || fi.Mode()&os.ModeCharDevice == 0 {
		t.Skipf("%s is not a character device here", os.DevNull)
	}
	for _, tt := range []struct {
		name    string
		noColor string
		term    string
		want    bool
	}{
		{"character device", "", "xterm-256color", true},
		{"NO_COLOR set", "1", "xterm-256color", false},
		{"NO_COLOR set to anything non-empty", "0", "xterm-256color", false},
		{"TERM=dumb", "", "dumb", false},
	} {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("NO_COLOR", tt.noColor)
			t.Setenv("TERM", tt.term)
			if got := enabled(dev); got != tt.want {
				t.Errorf("enabled() = %v, want %v", got, tt.want)
			}
		})
	}
}

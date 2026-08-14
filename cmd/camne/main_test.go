package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/officialdad/camne/internal/safety"
)

func TestRender(t *testing.T) {
	tests := []struct {
		name      string
		cmd       string
		wantWorst safety.Level
		wantErr   string // everything stderr may contain, byte for byte
	}{
		{"danger", "rm -rf /", safety.LevelDanger,
			"  camne warning: rm: target is the critical path /\n"},
		{"caution", "sudo apt update", safety.LevelCaution,
			"  camne warning: runs as root\n"},
		{"both levels share the one shape", "sudo rm -rf /", safety.LevelDanger,
			"  camne warning: runs as root\n" +
				"  camne warning: rm: target is the critical path /\n"},
		{"every finding gets a line", "rm -rf / ; shutdown -h now", safety.LevelDanger,
			"  camne warning: shuts the machine down\n" +
				"  camne warning: rm: target is the critical path /\n"},
		{"safe prints the command only", "ls -lah", safety.LevelSafe, ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			findings := safety.Check(tt.cmd)
			if got := safety.Worst(findings); got != tt.wantWorst {
				t.Fatalf("safety.Check(%q) worst = %v, want %v — the wiring test needs a command at that level",
					tt.cmd, got, tt.wantWorst)
			}
			var out, errw bytes.Buffer
			render(&out, &errw, tt.cmd, findings)

			// A buffer is not a terminal: the command must come out untouched
			// and nothing may be coloured.
			if out.String() != tt.cmd+"\n" {
				t.Errorf("stdout = %q, want just the command", out.String())
			}
			if errw.String() != tt.wantErr {
				t.Errorf("stderr = %q, want %q", errw.String(), tt.wantErr)
			}
			// One line per finding, no reason dropped.
			if n := strings.Count(errw.String(), "\n"); n != len(findings) {
				t.Errorf("stderr has %d lines, want one per finding (%d)", n, len(findings))
			}
		})
	}
}

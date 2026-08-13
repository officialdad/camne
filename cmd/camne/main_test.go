package main

import (
	"bytes"
	"testing"

	"github.com/officialdad/camne/internal/safety"
)

func TestRender(t *testing.T) {
	tests := []struct {
		name      string
		cmd       string
		wantWorst safety.Level
		wantErr   string // everything stderr may contain — one word, no reason, no advice
	}{
		{"danger gets one word", "rm -rf /", safety.LevelDanger, "!! BAHAYA\n"},
		{"caution gets one word", "sudo apt update", safety.LevelCaution, "!  Awas\n"},
		{"the worst level wins", "sudo rm -rf /", safety.LevelDanger, "!! BAHAYA\n"},
		{"two dangers still print once", "rm -rf / ; shutdown -h now", safety.LevelDanger, "!! BAHAYA\n"},
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
		})
	}
}

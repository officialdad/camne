package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/officialdad/camne/internal/safety"
)

func TestRender(t *testing.T) {
	tests := []struct {
		name       string
		cmd        string
		wantErrHas string // "" means stderr must be empty
		wantBanner bool
	}{
		{"danger gets BAHAYA banner", "rm -rf /", "!! BAHAYA", true},
		{"caution gets warning line", "sudo apt update", "Awas:", false},
		{"safe prints command only", "ls -lah", "", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			findings := safety.Check(tt.cmd)
			if tt.wantBanner && safety.Worst(findings) != safety.LevelDanger {
				t.Fatalf("safety.Check(%q) is not LevelDanger — wiring test needs a danger command", tt.cmd)
			}
			var out, errw bytes.Buffer
			render(&out, &errw, tt.cmd, findings)
			if out.String() != tt.cmd+"\n" {
				t.Errorf("stdout = %q, want just the command", out.String())
			}
			if tt.wantErrHas == "" {
				if errw.Len() != 0 {
					t.Errorf("stderr = %q, want empty", errw.String())
				}
			} else if !strings.Contains(errw.String(), tt.wantErrHas) {
				t.Errorf("stderr = %q, want it to contain %q", errw.String(), tt.wantErrHas)
			}
		})
	}
}

func TestAskConsent(t *testing.T) {
	tests := []struct {
		in   string
		want bool
	}{
		{"y\n", true},
		{"Y\n", true},
		{"ya\n", true},
		{"yes\n", true},
		{"  ok  \n", true},
		{"\n", false},  // empty line: default is no
		{"", false},    // closed stdin: no
		{"t\n", false}, // tidak
		{"tak\n", false},
		{"n\n", false},
		{"yolo\n", false},
	}
	for _, tt := range tests {
		if got := askConsent(strings.NewReader(tt.in)); got != tt.want {
			t.Errorf("askConsent(%q) = %v, want %v", tt.in, got, tt.want)
		}
	}
}

package main

import (
	"bytes"
	"strings"
	"testing"
	"unicode/utf8"

	"github.com/officialdad/camne/internal/safety"
)

func TestRender(t *testing.T) {
	tests := []struct {
		name      string
		cmd       string
		wantWorst safety.Level
		wantErr   []string // substrings stderr must contain, in this order
	}{
		{"danger gets the BAHAYA block", "rm -rf /", safety.LevelDanger, []string{
			"!! BAHAYA !!",                       // opening rule
			"laluan kritikal /",                  // the reason
			"tukar target ke folder",             // and what to do about it
			"tak jalankan apa-apa, dan tak akan", // the promise the whole tool rests on
			"!!!!",                               // closing rule
		}},
		{"caution gets a warning line", "sudo apt update", safety.LevelCaution, []string{
			"!  Awas: perlu sudo",
		}},
		{"both levels: the danger block comes first", "sudo rm -rf /", safety.LevelDanger, []string{
			"!! BAHAYA !!",
			"rm: target ialah laluan kritikal /",
			"!  Awas: perlu sudo",
		}},
		{"two dangers are counted", "rm -rf / ; shutdown -h now", safety.LevelDanger, []string{
			"!! BAHAYA (2 perkara) !!",
		}},
		{"safe prints the command only", "ls -lah", safety.LevelSafe, nil},
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
			if strings.Contains(errw.String(), "\x1b") {
				t.Errorf("stderr = %q, want no ANSI escapes for a non-terminal writer", errw.String())
			}
			if len(tt.wantErr) == 0 && errw.Len() != 0 {
				t.Errorf("stderr = %q, want empty", errw.String())
			}
			// Undo the block's word wrap first: these assertions are about
			// what the warning says, not where the lines happen to break.
			rest := strings.ReplaceAll(errw.String(), "\n   ", " ")
			for _, want := range tt.wantErr {
				i := strings.Index(rest, want)
				if i < 0 {
					t.Errorf("stderr = %q, want %q in it, after everything above", errw.String(), want)
					break
				}
				rest = rest[i+len(want):]
			}
		})
	}
}

// The block is only a block if every line fits inside the rule — an 80-column
// terminal wrapping one of them ragged is what this guards against.
func TestWrap(t *testing.T) {
	long := "rm: target ialah laluan kritikal /etc — tukar target ke folder yang kau betul-betul nak"
	for _, s := range []string{long, "pendek je", ""} {
		lines := wrap(s)
		for _, line := range lines {
			if n := utf8.RuneCountInString(line); n > ruleWidth {
				t.Errorf("wrap(%q) line %q is %d runes, want <= %d", s, line, n, ruleWidth)
			}
			if !strings.HasPrefix(line, "   ") {
				t.Errorf("wrap(%q) line %q is not indented into the block", s, line)
			}
		}
		if got := strings.Join(strings.Fields(strings.Join(lines, " ")), " "); got != strings.Join(strings.Fields(s), " ") {
			t.Errorf("wrap(%q) rejoins to %q — wrapping must not change the words", s, got)
		}
	}
	if n := len(wrap(long)); n < 2 {
		t.Errorf("wrap(long) produced %d line(s), want it split", n)
	}
}

func TestAdvice(t *testing.T) {
	tests := []struct {
		reason string
		want   string
	}{
		{"rm: target ialah laluan kritikal /etc", "tukar target ke folder yang kau betul-betul nak"},
		{"padam home directory kau", "tukar target ke folder yang kau betul-betul nak"},
		{"salurkan content dari internet terus masuk shell", "download dulu, baca sendiri, baru jalankan"},
		{"rm: target ialah placeholder -- laluan sebenar akan dipadam", "ganti placeholder tu dengan nama betul dulu"},
		{"fork bomb", "jangan jalankan sampai kau faham betul apa command ni buat"},
	}
	for _, tt := range tests {
		if got := advice(tt.reason); got != tt.want {
			t.Errorf("advice(%q) = %q, want %q", tt.reason, got, tt.want)
		}
	}
}

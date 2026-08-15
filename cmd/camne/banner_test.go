package main

import (
	"bytes"
	"strings"
	"testing"
)

// The wordmark is a picture made of characters: the spans have to line up into
// two rows of the same width, and the colour may not add or drop a glyph.
func TestBanner(t *testing.T) {
	var buf bytes.Buffer
	banner(&buf) // not a terminal, so this is the uncoloured shape
	lines := strings.Split(strings.TrimRight(buf.String(), "\n"), "\n")
	if len(lines) != 2 {
		t.Fatalf("got %d lines, want 2: %q", len(lines), buf.String())
	}
	if a, b := []rune(lines[0]), []rune(lines[1]); len(a) != len(b) {
		t.Errorf("rows are %d and %d glyphs wide, so the letters do not line up", len(a), len(b))
	}
	if strings.Contains(buf.String(), "\x1b") {
		t.Error("coloured a stream that is not a terminal")
	}

	// Colouring it changes nothing but the escapes around each span.
	var painted strings.Builder
	for _, row := range bannerRows {
		for i, span := range row {
			painted.WriteString(paint(true, logoHues[i], span))
		}
		painted.WriteString("\n")
	}
	if got := strip(painted.String()); got != strings.Join(lines, "\n")+"\n" {
		t.Errorf("colouring changed the shape:\n%q\n%q", got, buf.String())
	}
}

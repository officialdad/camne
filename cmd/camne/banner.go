package main

import (
	"fmt"
	"io"
	"strings"
)

// The camne wordmark, drawn in half-block characters and split into the three
// colour spans of the logo: the green page, the magenta brain, the cyan page
// (camne-hero-640x640.png). It marks the two moments camne changes what is on
// the disk — the first launch and an update — and appears nowhere else.
//
// ponytail: half-blocks (U+2580 block) assume a font with them, which every
// current terminal has and pre-1809 conhost's raster fonts do not. That host is
// out of support, same call as the escape sequences in color.go; a plain-text
// wordmark behind a runtime check is the upgrade path if a report turns up.
var bannerRows = [2][3]string{
	{"▛▘▀▌", "▛▛▌", "▛▌█▌"},
	{"▙▖█▌", "▌▌▌", "▌▌▙▖"},
}

// logoHues are the wordmark's colours, read off the logo rather than off the
// syntax palette — this is the one place a colour means camne itself instead of
// a piece of a command. Bold throughout: half-block glyphs read as flat colour,
// and one non-bold span between two bold ones looks like a rendering fault.
var logoHues = [3]string{cBinary, cWarn, "\x1b[1;36m"}

// banner draws the wordmark on w. Colour is asked of w exactly as everywhere
// else, so a piped or NO_COLOR run gets the plain characters — the shape is
// what carries the name, the colour only decorates it.
func banner(w io.Writer) {
	on := enabled(w)
	for _, row := range bannerRows {
		var b strings.Builder
		for i, span := range row {
			b.WriteString(paint(on, logoHues[i], span))
		}
		fmt.Fprintln(w, b.String())
	}
	fmt.Fprintln(w)
}

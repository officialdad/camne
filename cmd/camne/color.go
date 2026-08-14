package main

import (
	"io"
	"os"
	"strings"
)

// One fixed scheme, no themes and no 256-colour palette. These are the
// non-bright SGR codes, the ones a terminal theme is obliged to keep legible
// against its own background, so the same escapes read on light and dark.
const (
	reset   = "\x1b[0m"
	cBinary = "\x1b[1;32m" // bold green
	cFlag   = "\x1b[36m"   // cyan
	cPath   = "\x1b[35m"   // magenta
	cString = "\x1b[33m"   // yellow
	cOp     = "\x1b[1m"    // bold, no hue

	cDanger  = "\x1b[1;31m" // bold red, the BAHAYA block
	cCaution = "\x1b[33m"   // yellow, the Awas lines
)

// paint wraps s in code when on. Callers ask enabled() once per stream and pass
// the answer down, so one warning block cannot end up half coloured.
func paint(on bool, code, s string) string {
	if !on {
		return s
	}
	return code + s + reset
}

// enabled reports whether w is a terminal we may write escape sequences to.
// `camne ... | sh` and `$(camne ...)` are the normal way to use this tool, so
// anything that is not a character device gets today's plain bytes, unchanged.
// stdout and stderr are asked separately: piping the command into a shell still
// leaves the warnings on a terminal.
//
// Windows: we deliberately do NOT call kernel32.SetConsoleMode to switch on
// ENABLE_VIRTUAL_TERMINAL_PROCESSING from a color_windows.go. Windows Terminal
// and Windows 10 1809+ conhost enable it themselves; the only host left that
// would print raw escape bytes is pre-1809 conhost, which is out of support.
// That is a cosmetic problem on a dead platform, and the fix costs a syscall
// file plus a second code path. Add it if a real report ever turns up.
func enabled(w io.Writer) bool {
	if os.Getenv("NO_COLOR") != "" || os.Getenv("TERM") == "dumb" {
		return false
	}
	f, ok := w.(*os.File)
	return ok && isTTY(f)
}

// isTTY reports whether f is a character device, which is the portable
// stand-in for "a person is on the other end of this". Colour asks it, and so
// does the update prompt — one check, so the two can never disagree about
// whether camne is being piped somewhere.
func isTTY(f *os.File) bool {
	fi, err := f.Stat()
	return err == nil && fi.Mode()&os.ModeCharDevice != 0
}

// highlight colours the shape of a command line: binary, flags, paths, quoted
// strings, shell operators, everything else plain.
//
// It spans the ORIGINAL bytes — every byte of cmd is written back exactly once,
// in order — so stripping the escapes returns cmd. That is why safety's
// shlexSplit is not reused: it drops quotes and resolves escapes by design, and
// what it returns can no longer be pasted into a shell.
func highlight(cmd string) string {
	var b strings.Builder
	head := true // the next word is the binary being run
	for i := 0; i < len(cmd); {
		if c := cmd[i]; c == ' ' || c == '\t' {
			b.WriteByte(c)
			i++
			continue
		}
		j := tokenEnd(cmd, i)
		tok := cmd[i:j]
		if isOpByte(tok[0]) {
			b.WriteString(cOp + tok + reset)
			// A pipe or `&&` starts a new command; a redirect does not — the
			// word after `>` is a file, not a binary.
			head = !strings.ContainsAny(tok, "<>")
		} else {
			if c := colorOf(tok, head); c != "" {
				b.WriteString(c + tok + reset)
			} else {
				b.WriteString(tok)
			}
			head = false
		}
		i = j
	}
	return b.String()
}

const opChars = "|&;<>"

func isOpByte(c byte) bool { return strings.IndexByte(opChars, c) >= 0 }

func colorOf(tok string, head bool) string {
	switch {
	case head:
		return cBinary
	case tok[0] == '\'' || tok[0] == '"':
		return cString
	case tok[0] == '-':
		return cFlag
	case tok[0] == '/' || tok[0] == '~' || tok[0] == '.' || strings.Contains(tok, "/"):
		return cPath
	}
	return ""
}

// tokenEnd returns the index one past the token starting at i, which is never i
// itself. A run of operator characters is one token; otherwise the token runs to
// whitespace or an operator, with quotes and backslash escapes spanned whole so
// `'a b'` stays a single string.
func tokenEnd(s string, i int) int {
	j := i
	if isOpByte(s[j]) {
		for j < len(s) && isOpByte(s[j]) {
			j++
		}
		return j
	}
	for j < len(s) {
		c := s[j]
		switch {
		case c == ' ' || c == '\t' || isOpByte(c):
			return j
		case c == '\'' || c == '"':
			j = closeQuote(s, j)
		case c == '\\' && j+1 < len(s):
			j += 2
		default:
			j++
		}
	}
	return j
}

// closeQuote returns the index one past the quote opened at i, or len(s) when it
// is never closed. Only double quotes honour backslash escapes, as in a shell.
func closeQuote(s string, i int) int {
	q := s[i]
	for j := i + 1; j < len(s); j++ {
		if q == '"' && s[j] == '\\' && j+1 < len(s) {
			j++
			continue
		}
		if s[j] == q {
			return j + 1
		}
	}
	return len(s)
}

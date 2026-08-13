// camne turns plain Malay into a shell command.
//
// The query path: make sure llama-server and the model are provisioned
// (downloading them on first run, size announced up front), ask the resident
// model, safety-check the answer, and PRINT it. Nothing is ever executed
// (constraint 5).
package main

import (
	"fmt"
	"io"
	"os"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/officialdad/camne/internal/engine"
	"github.com/officialdad/camne/internal/provision"
	"github.com/officialdad/camne/internal/safety"
)

// version is stamped by scripts/build.sh via -ldflags.
var version = "dev"

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		usage()
		os.Exit(1)
	}
	switch args[0] {
	case "--version", "-v":
		fmt.Println("camne " + version)
		return
	case "doctor":
		doctor()
		return
	case "stop":
		stop()
		return
	}
	os.Exit(run(strings.Join(args, " ")))
}

// run answers one query end to end. Errors from the packages below are
// already colloquial Malay, so they are printed as-is.
func run(query string) int {
	st, err := provision.GetStatus()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if !st.ServerOK || !st.ModelOK {
		if !ensureProvisioned(st) {
			return 1
		}
	}
	cli, cold, err := engine.Connect(st.ServerPath, st.ModelPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if cold {
		fmt.Fprintln(os.Stderr, "Sekejap ya — model tengah load. Soalan pertama je yang lambat sikit.")
	}
	if err := cli.WaitReady(2 * time.Minute); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	cmd, err := cli.Complete(query)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	render(os.Stdout, os.Stderr, cmd, safety.Check(cmd))
	return 0
}

// render prints safety warnings to errw and the command itself to out — and
// that is ALL camne ever does with a command: print it. Danger findings get
// the BAHAYA block and must never be auto-run (constraint 5).
//
// Each stream is asked about colour on its own: stdout is usually piped into a
// shell while stderr is still the terminal the user is reading. The command is
// highlighted only when out is a terminal, so `camne ... | sh` still receives
// exactly the bytes it did before.
func render(out, errw io.Writer, cmd string, findings []safety.Finding) {
	var dangers, cautions []safety.Finding
	for _, f := range findings {
		switch f.Level {
		case safety.LevelDanger:
			dangers = append(dangers, f)
		case safety.LevelCaution:
			cautions = append(cautions, f)
		}
	}
	warn := enabled(errw)
	if len(dangers) > 0 {
		head := "BAHAYA"
		if len(dangers) > 1 {
			head = fmt.Sprintf("BAHAYA (%d perkara)", len(dangers))
		}
		fmt.Fprintln(errw, paint(warn, cDanger, rule(head)))
		for _, f := range dangers {
			for _, line := range wrap(f.Reason + " — " + advice(f.Reason)) {
				fmt.Fprintln(errw, paint(warn, cDanger, line))
			}
		}
		for _, line := range wrap("camne cuma tunjuk command ni je — ia tak jalankan apa-apa, dan tak akan.") {
			fmt.Fprintln(errw, line)
		}
		fmt.Fprintln(errw, paint(warn, cDanger, rule("")))
	}
	for _, f := range cautions {
		fmt.Fprintln(errw, paint(warn, cCaution, "  !  Awas: "+f.Reason))
	}
	if enabled(out) {
		cmd = highlight(cmd)
	}
	fmt.Fprintln(out, cmd)
}

// rule draws an edge of the danger block: `!! BAHAYA !!!!...` on top, a plain
// run of `!` underneath. ASCII, because the box-drawing characters garble on an
// old Windows console and this is the one message that must always be readable.
func rule(label string) string {
	if label == "" {
		return strings.Repeat("!", ruleWidth)
	}
	s := "!! " + label + " "
	return s + strings.Repeat("!", max(0, ruleWidth-len(s)))
}

const ruleWidth = 60

// wrap breaks one line of the danger block at word boundaries so it stays
// inside the rule instead of spilling ragged past it on an 80-column terminal,
// and indents every line to the block's three spaces. Counted in runes, not
// bytes, because the em dash in these strings is three bytes wide and one
// column. A word longer than the width is left over-long rather than cut in
// half — a truncated path is worse than an untidy block.
func wrap(s string) []string {
	const indent = "   "
	var lines []string
	line := indent
	for _, word := range strings.Fields(s) {
		switch {
		case line == indent:
			line += word
		case utf8.RuneCountInString(line+" "+word) <= ruleWidth:
			line += " " + word
		default:
			lines = append(lines, line)
			line = indent + word
		}
	}
	return append(lines, line)
}

// advice turns a diagnosis into an instruction, because an error message has to
// say what to do next. It reads the Reason wording rather than the detection
// logic, which it must not touch; an unmatched reason falls through to the
// generic line, so a new rule in internal/safety degrades quietly.
func advice(reason string) string {
	switch {
	case strings.Contains(reason, "kritikal") || strings.Contains(reason, "home directory"):
		return "tukar target ke folder yang kau betul-betul nak"
	case strings.Contains(reason, "internet") || strings.Contains(reason, "remote"):
		return "download dulu, baca sendiri, baru jalankan"
	case strings.Contains(reason, "placeholder"):
		return "ganti placeholder tu dengan nama betul dulu"
	}
	return "jangan jalankan sampai kau faham betul apa command ni buat"
}

// stop shuts the resident llama-server down.
func stop() {
	stopped, err := engine.Stop()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if stopped {
		fmt.Println("Ok, llama-server dah dihentikan.")
	} else {
		fmt.Println("Takde llama-server yang tengah jalan pun.")
	}
}

// doctor reports what is provisioned and what is missing. Diagnostic only —
// it changes nothing on disk.
func doctor() {
	st, err := provision.GetStatus()
	if err != nil {
		fmt.Fprintln(os.Stderr, err) // provision errors are already in Malay
		os.Exit(1)
	}
	mark := func(ok bool) string {
		if ok {
			return "[ada]   "
		}
		return "[tiada] "
	}
	fmt.Println("camne doctor — semak apa yang camne perlukan")
	fmt.Println()
	fmt.Println(mark(st.ServerOK) + "llama-server : " + st.ServerPath)
	fmt.Printf("%smodel        : %s (lebih kurang %d MB)\n",
		mark(st.ModelOK), st.ModelPath, provision.ModelSize/1_000_000)
	if st.LibcNote != "" {
		fmt.Println()
		fmt.Println("Perhatian: " + st.LibcNote)
	}
	fmt.Println()
	if st.ServerOK && st.ModelOK {
		fmt.Println("Semua lengkap — camne sedia untuk digunakan.")
		return
	}
	fmt.Println("Taip je soalan anda — camne download sendiri apa yang tiada dulu,")
	fmt.Println("lepas tu terus jawab.")
}

func usage() {
	fmt.Fprint(os.Stderr, `camne — tanya dalam BM, dapat shell command.

Guna:    camne <soalan anda>
Contoh:  camne nak buat file baru
         camne cari file dalam folder ni

Lain:    camne doctor   — semak apa yang dah dipasang
         camne stop     — hentikan model yang duduk dalam memory

camne hanya tunjuk command — ia tak jalankan apa-apa.
`)
}

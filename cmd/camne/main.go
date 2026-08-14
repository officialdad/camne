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

// render prints the safety findings to errw and the command itself to out —
// and that is ALL camne ever does with a command: print it. A flagged command
// must never be auto-run (constraint 5).
//
// Every finding gets its own line, prefixed with the tool's own name so a
// beginner can tell camne talking from the command it just produced. Danger and
// caution share one shape and one colour on purpose: the reason is what says how
// bad it is, so the reason is what gets printed.
//
// Each stream is asked about colour on its own: stdout is usually piped into a
// shell while stderr is still the terminal the user is reading. The command is
// highlighted only when out is a terminal, so `camne ... | sh` still receives
// exactly the bytes it did before.
func render(out, errw io.Writer, cmd string, findings []safety.Finding) {
	on := enabled(errw)
	for _, f := range findings {
		fmt.Fprintln(errw, "  "+paint(on, cWarn, "camne warning: "+f.Reason))
	}
	if enabled(out) {
		cmd = highlight(cmd)
	}
	fmt.Fprintln(out, cmd)
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

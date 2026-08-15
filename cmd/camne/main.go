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
	code := 0
	switch args[0] {
	case "--version", "-v":
		fmt.Println("camne " + version)
	case "doctor":
		doctor()
	case "stop":
		stop()
	case "update":
		os.Exit(update()) // asked for explicitly: no offer, no throttle
	default:
		code = run(strings.Join(args, " "))
	}
	// Only now, with the answer already printed, does camne look at the
	// network for a newer release (constraint 3) — and only if that answer
	// worked. Someone whose command just failed is owed the error, not an
	// offer to install a different version of the thing that failed.
	if code == 0 {
		offerUpdate()
	}
	os.Exit(code)
}

// run answers one query end to end. Errors from the packages below are
// already written for the person at the prompt, so they are printed as-is.
func run(query string) int {
	st, err := provision.GetStatus()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if !st.ServerOK || !st.ModelOK() {
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
		fmt.Fprintln(os.Stderr, "One moment — the model is loading. Only the first question is this slow.")
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
	// A blank line so the warning block never reads as the first line of the
	// command. It goes to errw, not out: a piped stdout keeps its exact bytes.
	if len(findings) > 0 {
		fmt.Fprintln(errw)
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
		fmt.Println("Ok, llama-server has been shut down.")
	} else {
		fmt.Println("There was no llama-server running.")
	}
}

// doctor reports what is provisioned and what is missing. Diagnostic only —
// it changes nothing on disk.
func doctor() {
	st, err := provision.GetStatus()
	if err != nil {
		fmt.Fprintln(os.Stderr, err) // provision errors are already written for the user
		os.Exit(1)
	}
	// One padded tag column for both lines: the model has more to say than
	// found-or-missing, and "missing" for a file sitting on disk is a lie.
	tag := func(word string) string { return fmt.Sprintf("%-14s", "["+word+"]") }
	serverWord := "missing"
	if st.ServerOK {
		serverWord = "found"
	}
	fmt.Println("camne doctor — what camne needs, and what it already has")
	fmt.Println()
	fmt.Println(tag(serverWord) + "llama-server : " + st.ServerPath)
	fmt.Printf("%smodel        : %s (about %d MB)\n",
		tag(st.Model.String()), st.ModelPath, provision.ModelSize/1_000_000)
	if st.LibcNote != "" {
		fmt.Println()
		fmt.Println("Heads up: " + st.LibcNote)
	}
	fmt.Println()
	if st.ServerOK && st.ModelOK() {
		fmt.Println("All set — camne is ready to use.")
		return
	}
	var note string
	switch st.Model {
	case provision.ModelStale:
		note = "The model on this computer is an older one than this camne expects."
	case provision.ModelUnrecorded:
		note = "The model on this computer was saved before camne started recording\n" +
			"checksums, so camne has to check it once before trusting it."
	case provision.ModelDamaged:
		note = "The model file is the wrong size — a download that was cut off."
	}
	if note != "" {
		fmt.Println(note)
		fmt.Println()
	}
	fmt.Println("Just type your question — camne sorts this out first, then answers.")
}

func usage() {
	fmt.Fprint(os.Stderr, `camne — ask in plain Malay or English, get a shell command.

Use:      camne <your question>
Examples: camne nak buat file baru
          camne how do I find a file in this folder

Also:     camne doctor   — check what is already installed
          camne stop     — shut down the model sitting in memory
          camne update   — check for a newer camne and install it

camne only shows you the command — it never runs anything.
`)
}

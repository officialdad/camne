// camne turns plain Malay into a shell command.
//
// Milestone 1 skeleton: a hardcoded keyword table stands in for the model.
// It only ever prints a command; nothing is executed.
package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/officialdad/camne/internal/provision"
)

// version is stamped by scripts/build.sh via -ldflags.
var version = "dev"

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		usage()
		os.Exit(1)
	}
	if args[0] == "--version" || args[0] == "-v" {
		fmt.Println("camne " + version)
		return
	}
	if args[0] == "doctor" {
		doctor()
		return
	}
	q := strings.ToLower(strings.Join(args, " "))
	cmd, ok := guess(q)
	if !ok {
		fmt.Fprintln(os.Stderr, "camne belum faham soalan tu lagi — model penuh datang dalam versi seterusnya.")
		fmt.Fprintln(os.Stderr, "Cuba contoh: camne nak buat file baru")
		os.Exit(1)
	}
	fmt.Println(cmd)
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
	fmt.Println("Tak perlu buat apa-apa sekarang: bila engine siap (versi seterusnya),")
	fmt.Println("camne akan tanya kebenaran anda dulu, lepas tu download sendiri apa yang tiada.")
}

func usage() {
	fmt.Fprint(os.Stderr, `camne — tanya dalam BM, dapat shell command.

Guna:    camne <soalan anda>
Contoh:  camne nak buat file baru
         camne cari file dalam folder ni

Lain:    camne doctor   — semak apa yang dah dipasang

camne hanya tunjuk command — ia tak jalankan apa-apa.
`)
}

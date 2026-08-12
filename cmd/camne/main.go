// camne turns plain Malay into a shell command.
//
// Milestone 1 skeleton: a hardcoded keyword table stands in for the model.
// It only ever prints a command; nothing is executed.
package main

import (
	"fmt"
	"os"
	"strings"
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
	q := strings.ToLower(strings.Join(args, " "))
	cmd, ok := guess(q)
	if !ok {
		fmt.Fprintln(os.Stderr, "camne belum faham soalan tu lagi — model penuh datang dalam versi seterusnya.")
		fmt.Fprintln(os.Stderr, "Cuba contoh: camne nak buat file baru")
		os.Exit(1)
	}
	fmt.Println(cmd)
}

func usage() {
	fmt.Fprint(os.Stderr, `camne — tanya dalam BM, dapat shell command.

Guna:    camne <soalan anda>
Contoh:  camne nak buat file baru
         camne cari file dalam folder ni

camne hanya tunjuk command — ia tak jalankan apa-apa.
`)
}

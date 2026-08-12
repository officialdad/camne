package provision

import (
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
)

// llama.cpp release binaries for Linux are built on Ubuntu and need
// glibc >= 2.34; on musl (Alpine) they do not start at all.
const glibcMinMajor, glibcMinMinor = 2, 34

// ponytail: no compatibility build is pinned yet — older glibc and musl only
// get a diagnosis, not a fix. Upgrade path: pin a static/compat llama.cpp
// build (as whatisit's fetch.py does) and select it here.

// libcNote returns a colloquial-Malay note when this machine's libc cannot
// run the prebuilt llama.cpp, or "" when it can (or this is not Linux).
func libcNote() string {
	if runtime.GOOS != "linux" {
		return ""
	}
	out, err := exec.Command("ldd", "--version").CombinedOutput()
	if err != nil && len(out) == 0 {
		// No ldd at all — usually musl or a container image stripped bare.
		if m, _ := filepath.Glob("/lib/ld-musl-*"); len(m) > 0 {
			return "sistem ni guna musl (macam Alpine) — llama-server prebuilt tak akan jalan kat sini"
		}
		return "tak dapat kesan versi glibc — kalau llama-server tak jalan nanti, ini mungkin sebabnya"
	}
	musl, major, minor, ok := parseLddVersion(string(out))
	switch {
	case musl:
		return "sistem ni guna musl (macam Alpine) — llama-server prebuilt tak akan jalan kat sini"
	case !ok:
		return "tak dapat kesan versi glibc — kalau llama-server tak jalan nanti, ini mungkin sebabnya"
	case major < glibcMinMajor || (major == glibcMinMajor && minor < glibcMinMinor):
		return "glibc " + strconv.Itoa(major) + "." + strconv.Itoa(minor) +
			" terlalu lama (perlu 2.34 ke atas) — llama-server prebuilt tak akan jalan kat sini"
	}
	return ""
}

// parseLddVersion reads `ldd --version` output. glibc prints a first line
// like "ldd (Ubuntu GLIBC 2.35-0ubuntu3.8) 2.35" or "ldd (GNU libc) 2.34";
// the version is the last field. musl prints "musl libc (...)" instead.
func parseLddVersion(out string) (musl bool, major, minor int, ok bool) {
	if strings.Contains(out, "musl") {
		return true, 0, 0, true
	}
	line, _, _ := strings.Cut(out, "\n")
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return false, 0, 0, false
	}
	ver := fields[len(fields)-1]
	majS, minS, found := strings.Cut(ver, ".")
	if !found {
		return false, 0, 0, false
	}
	// Trim any packaging suffix after the minor number, e.g. "2.35-0ubuntu3".
	if i := strings.IndexFunc(minS, func(r rune) bool { return r < '0' || r > '9' }); i >= 0 {
		minS = minS[:i]
	}
	major, errA := strconv.Atoi(majS)
	minor, errB := strconv.Atoi(minS)
	if errA != nil || errB != nil {
		return false, 0, 0, false
	}
	return false, major, minor, true
}

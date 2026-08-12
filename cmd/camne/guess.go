package main

import "strings"

// ponytail: hardcoded keyword table, replaced by the local model at milestone 3.
// Order matters: destructive/specific verbs first so "padam file" never falls
// through to a "file" rule.
var rules = []struct {
	any []string // query matches if it contains any of these
	cmd string
}{
	{[]string{"padam", "buang", "delete", "remove"}, "rm nama_fail.txt"},
	{[]string{"cari", "search", "find"}, `find . -name "nama_fail*"`},
	{[]string{"buat folder", "folder baru", "create folder"}, "mkdir nama_folder"},
	{[]string{"buat file", "file baru", "fail baru", "create file"}, "touch nama_fail.txt"},
	{[]string{"senarai", "tengok", "list"}, "ls -lah"},
	{[]string{"salin", "copy"}, "cp sumber destinasi"},
	{[]string{"pindah", "tukar nama", "move", "rename"}, "mv nama_lama nama_baru"},
	{[]string{"muat turun", "download"}, "curl -O URL"},
	{[]string{"mampat", "zip", "compress"}, "tar -czf arkib.tar.gz nama_folder"},
	{[]string{"extract", "unzip"}, "tar -xzf arkib.tar.gz"},
}

func guess(q string) (string, bool) {
	for _, r := range rules {
		for _, k := range r.any {
			if strings.Contains(q, k) {
				return r.cmd, true
			}
		}
	}
	return "", false
}

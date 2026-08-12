package main

import "testing"

func TestGuess(t *testing.T) {
	tests := []struct {
		q   string
		cmd string
		ok  bool
	}{
		{"nak buat file baru", "touch nama_fail.txt", true},
		{"macam mana nak buat folder baru", "mkdir nama_folder", true},
		{"nak padam file ni", "rm nama_fail.txt", true},
		{"tolong buang file tu", "rm nama_fail.txt", true},
		{"cari file baru", `find . -name "nama_fail*"`, true}, // "cari" wins over "file baru"
		{"list semua file", "ls -lah", true},
		{"download file dari server", "curl -O URL", true},
		{"apa khabar dunia", "", false},
	}
	for _, tt := range tests {
		cmd, ok := guess(tt.q)
		if ok != tt.ok || cmd != tt.cmd {
			t.Errorf("guess(%q) = %q, %v; want %q, %v", tt.q, cmd, ok, tt.cmd, tt.ok)
		}
	}
}

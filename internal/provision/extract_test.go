package provision

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func keepAll(string) bool { return true }

func writeZip(t *testing.T, entries map[string]string) string {
	t.Helper()
	var buf bytes.Buffer
	w := zip.NewWriter(&buf)
	for name, body := range entries {
		f, err := w.CreateHeader(&zip.FileHeader{Name: name})
		if err != nil {
			t.Fatal(err)
		}
		f.Write([]byte(body))
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(t.TempDir(), "a.zip")
	if err := os.WriteFile(p, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

type tarEntry struct {
	name, body, link string
	mode             int64
}

func writeTarGz(t *testing.T, entries []tarEntry) string {
	t.Helper()
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gz)
	for _, e := range entries {
		hdr := &tar.Header{Name: e.name, Mode: e.mode}
		if hdr.Mode == 0 {
			hdr.Mode = 0o644
		}
		if e.link != "" {
			hdr.Typeflag = tar.TypeSymlink
			hdr.Linkname = e.link
		} else {
			hdr.Typeflag = tar.TypeReg
			hdr.Size = int64(len(e.body))
		}
		if err := tw.WriteHeader(hdr); err != nil {
			t.Fatal(err)
		}
		if e.link == "" {
			tw.Write([]byte(e.body))
		}
	}
	if err := tw.Close(); err != nil {
		t.Fatal(err)
	}
	if err := gz.Close(); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(t.TempDir(), "a.tar.gz")
	if err := os.WriteFile(p, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestExtractZip(t *testing.T) {
	tests := []struct {
		name    string
		entries map[string]string
		keep    func(string) bool
		wantErr bool
		present []string
		absent  []string
	}{
		{
			name:    "plain entries extract",
			entries: map[string]string{"bin/llama-server.exe": "exe", "bin/lib.dll": "dll"},
			keep:    keepAll,
			present: []string{"bin/llama-server.exe", "bin/lib.dll"},
		},
		{
			name:    "keep filters entries",
			entries: map[string]string{"bin/llama-server.exe": "exe", "docs/readme.txt": "no"},
			keep:    func(n string) bool { return n != "docs/readme.txt" },
			present: []string{"bin/llama-server.exe"},
			absent:  []string{"docs/readme.txt"},
		},
		{
			name:    "dot-dot traversal rejected",
			entries: map[string]string{"../evil.txt": "x"},
			keep:    keepAll,
			wantErr: true,
		},
		{
			name:    "nested dot-dot traversal rejected",
			entries: map[string]string{"a/../../evil.txt": "x"},
			keep:    keepAll,
			wantErr: true,
		},
		{
			name:    "absolute path rejected",
			entries: map[string]string{"/etc/evil.txt": "x"},
			keep:    keepAll,
			wantErr: true,
		},
		{
			name:    "backslash name rejected",
			entries: map[string]string{`..\evil.txt`: "x"},
			keep:    keepAll,
			wantErr: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			archive := writeZip(t, tt.entries)
			dest := t.TempDir()
			err := ExtractZip(archive, dest, tt.keep)
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("ExtractZip: %v", err)
			}
			for _, p := range tt.present {
				if _, err := os.Stat(filepath.Join(dest, filepath.FromSlash(p))); err != nil {
					t.Errorf("%s missing: %v", p, err)
				}
			}
			for _, p := range tt.absent {
				if _, err := os.Stat(filepath.Join(dest, filepath.FromSlash(p))); err == nil {
					t.Errorf("%s present, should not be", p)
				}
			}
		})
	}
}

func TestExtractTarGz(t *testing.T) {
	tests := []struct {
		name    string
		entries []tarEntry
		keep    func(string) bool
		wantErr bool
		present []string
		absent  []string
	}{
		{
			name: "files and internal symlink extract",
			entries: []tarEntry{
				{name: "bin/llama-server", body: "exe", mode: 0o755},
				{name: "bin/libllama.so.0", body: "so", mode: 0o644},
				{name: "bin/libllama.so", link: "libllama.so.0"},
			},
			keep:    keepAll,
			present: []string{"bin/llama-server", "bin/libllama.so.0", "bin/libllama.so"},
		},
		{
			name: "keep filters entries",
			entries: []tarEntry{
				{name: "bin/llama-server", body: "exe", mode: 0o755},
				{name: "docs/readme", body: "no"},
			},
			keep:    func(n string) bool { return n == "bin/llama-server" },
			present: []string{"bin/llama-server"},
			absent:  []string{"docs/readme"},
		},
		{
			name:    "dot-dot traversal rejected",
			entries: []tarEntry{{name: "../evil", body: "x"}},
			keep:    keepAll,
			wantErr: true,
		},
		{
			name:    "absolute path rejected",
			entries: []tarEntry{{name: "/etc/evil", body: "x"}},
			keep:    keepAll,
			wantErr: true,
		},
		{
			name:    "symlink escaping destDir rejected",
			entries: []tarEntry{{name: "bin/escape", link: "../../outside"}},
			keep:    keepAll,
			wantErr: true,
		},
		{
			name:    "symlink with absolute target rejected",
			entries: []tarEntry{{name: "bin/escape", link: "/etc/passwd"}},
			keep:    keepAll,
			wantErr: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			archive := writeTarGz(t, tt.entries)
			dest := t.TempDir()
			err := ExtractTarGz(archive, dest, tt.keep)
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("ExtractTarGz: %v", err)
			}
			for _, p := range tt.present {
				if _, err := os.Lstat(filepath.Join(dest, filepath.FromSlash(p))); err != nil {
					t.Errorf("%s missing: %v", p, err)
				}
			}
			for _, p := range tt.absent {
				if _, err := os.Lstat(filepath.Join(dest, filepath.FromSlash(p))); err == nil {
					t.Errorf("%s present, should not be", p)
				}
			}
		})
	}
}

func TestExtractTarGzPreservesExecBit(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("no unix permission bits on windows")
	}
	archive := writeTarGz(t, []tarEntry{{name: "bin/llama-server", body: "exe", mode: 0o755}})
	dest := t.TempDir()
	if err := ExtractTarGz(archive, dest, keepAll); err != nil {
		t.Fatal(err)
	}
	fi, err := os.Stat(filepath.Join(dest, "bin", "llama-server"))
	if err != nil {
		t.Fatal(err)
	}
	if fi.Mode().Perm()&0o100 == 0 {
		t.Errorf("exec bit lost: mode %v", fi.Mode())
	}
}

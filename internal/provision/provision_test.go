package provision

import "testing"

func TestLlamaAsset(t *testing.T) {
	tests := []struct {
		goos, goarch string
		want         string // asset name, "" = expect error
	}{
		{"linux", "amd64", "llama-" + llamaBuild + "-bin-ubuntu-x64.tar.gz"},
		{"linux", "arm64", "llama-" + llamaBuild + "-bin-ubuntu-arm64.tar.gz"},
		{"darwin", "amd64", "llama-" + llamaBuild + "-bin-macos-x64.tar.gz"},
		{"darwin", "arm64", "llama-" + llamaBuild + "-bin-macos-arm64.tar.gz"},
		{"windows", "amd64", "llama-" + llamaBuild + "-bin-win-cpu-x64.zip"},
		{"windows", "arm64", "llama-" + llamaBuild + "-bin-win-cpu-arm64.zip"},
		{"linux", "386", ""},
		{"plan9", "amd64", ""},
	}
	for _, tt := range tests {
		a, err := LlamaAsset(tt.goos, tt.goarch)
		if tt.want == "" {
			if err == nil {
				t.Errorf("%s/%s: expected error, got %q", tt.goos, tt.goarch, a.Name)
			}
			continue
		}
		if err != nil {
			t.Errorf("%s/%s: %v", tt.goos, tt.goarch, err)
			continue
		}
		if a.Name != tt.want {
			t.Errorf("%s/%s: got %q, want %q", tt.goos, tt.goarch, a.Name, tt.want)
		}
		if len(a.SHA256) != 64 || a.Size <= 0 {
			t.Errorf("%s/%s: incomplete pin: sha256 len %d, size %d", tt.goos, tt.goarch, len(a.SHA256), a.Size)
		}
	}
}

func TestParseLddVersion(t *testing.T) {
	tests := []struct {
		name         string
		out          string
		musl         bool
		major, minor int
		ok           bool
	}{
		{
			name:  "ubuntu glibc",
			out:   "ldd (Ubuntu GLIBC 2.35-0ubuntu3.8) 2.35\nCopyright (C) 2022 Free Software Foundation, Inc.\n",
			major: 2, minor: 35, ok: true,
		},
		{
			name:  "plain gnu libc",
			out:   "ldd (GNU libc) 2.31\n",
			major: 2, minor: 31, ok: true,
		},
		{
			name:  "new enough",
			out:   "ldd (GNU libc) 2.34\n",
			major: 2, minor: 34, ok: true,
		},
		{
			name: "musl",
			out:  "musl libc (x86_64)\nVersion 1.2.4\n",
			musl: true, ok: true,
		},
		{name: "garbage", out: "command not found\n"},
		{name: "empty", out: ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			musl, major, minor, ok := parseLddVersion(tt.out)
			if musl != tt.musl || major != tt.major || minor != tt.minor || ok != tt.ok {
				t.Errorf("got (%v, %d, %d, %v), want (%v, %d, %d, %v)",
					musl, major, minor, ok, tt.musl, tt.major, tt.minor, tt.ok)
			}
		})
	}
}

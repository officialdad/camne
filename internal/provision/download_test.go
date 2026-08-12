package provision

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func sum(b []byte) string {
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}

func TestDownload(t *testing.T) {
	payload := bytes.Repeat([]byte("camne-payload-0123456789"), 100) // 2400 bytes

	tests := []struct {
		name       string
		part       []byte // pre-existing .part content, nil = none
		rangeOK    bool   // server honours Range requests
		want       string // expected sha256 passed to Download
		wantErr    bool
		wantRange  string // Range header the server must have seen
		wantOnDisk bool   // dest exists with payload afterwards
		partStays  bool   // .part still present afterwards
	}{
		{
			name:       "fresh download",
			rangeOK:    true,
			want:       sum(payload),
			wantOnDisk: true,
		},
		{
			name:       "resume from partial",
			part:       payload[:100],
			rangeOK:    true,
			want:       sum(payload),
			wantRange:  "bytes=100-",
			wantOnDisk: true,
		},
		{
			name:       "server ignores Range, restart from scratch",
			part:       []byte("stale garbage that must be thrown away"),
			rangeOK:    false,
			want:       sum(payload),
			wantOnDisk: true,
		},
		{
			name:       "part already complete (416), verify and rename",
			part:       payload,
			rangeOK:    true,
			want:       sum(payload),
			wantOnDisk: true,
		},
		{
			name:    "checksum mismatch deletes the partial",
			rangeOK: true,
			want:    sum([]byte("not the payload")),
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var gotRange string
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				gotRange = r.Header.Get("Range")
				if tt.rangeOK {
					http.ServeContent(w, r, "f", time.Time{}, bytes.NewReader(payload))
					return
				}
				w.Write(payload)
			}))
			defer srv.Close()

			dest := filepath.Join(t.TempDir(), "file.bin")
			if tt.part != nil {
				if err := os.WriteFile(dest+".part", tt.part, 0o644); err != nil {
					t.Fatal(err)
				}
			}

			err := Download(srv.URL, dest, tt.want)
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
			} else if err != nil {
				t.Fatalf("Download: %v", err)
			}

			if tt.wantRange != "" && gotRange != tt.wantRange {
				t.Errorf("Range header = %q, want %q", gotRange, tt.wantRange)
			}
			got, statErr := os.ReadFile(dest)
			if tt.wantOnDisk {
				if statErr != nil {
					t.Fatalf("dest missing: %v", statErr)
				}
				if !bytes.Equal(got, payload) {
					t.Errorf("dest content wrong: %d bytes, want %d", len(got), len(payload))
				}
			} else if statErr == nil {
				t.Error("dest exists, should not")
			}
			if _, err := os.Stat(dest + ".part"); (err == nil) != tt.partStays {
				t.Errorf(".part present = %v, want %v", err == nil, tt.partStays)
			}
		})
	}
}

func TestDownloadHTTPError(t *testing.T) {
	srv := httptest.NewServer(http.NotFoundHandler())
	defer srv.Close()
	dest := filepath.Join(t.TempDir(), "file.bin")
	if err := Download(srv.URL, dest, sum(nil)); err == nil {
		t.Fatal("expected error on HTTP 404, got nil")
	}
	if _, err := os.Stat(dest); err == nil {
		t.Error("dest exists after failed download")
	}
}

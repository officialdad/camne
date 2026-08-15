package provision

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync"
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

			err := Download(srv.URL, dest, int64(len(payload)), tt.want)
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
	if err := Download(srv.URL, dest, 0, sum(nil)); err == nil {
		t.Fatal("expected error on HTTP 404, got nil")
	}
	if _, err := os.Stat(dest); err == nil {
		t.Error("dest exists after failed download")
	}
}

// withSmallParallelMin makes the split path reachable without moving 64 MB
// around in a unit test.
func withSmallParallelMin(t *testing.T, n int64) {
	t.Helper()
	old := parallelMin
	parallelMin = n
	t.Cleanup(func() { parallelMin = old })
}

func TestDownloadParallel(t *testing.T) {
	// Not a multiple of parallelStreams: the last segment must carry the
	// remainder, or the file comes back short.
	payload := bytes.Repeat([]byte("camne"), 481) // 2405 bytes
	withSmallParallelMin(t, 100)

	var mu sync.Mutex
	var ranges []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		ranges = append(ranges, r.Header.Get("Range"))
		mu.Unlock()
		http.ServeContent(w, r, "f", time.Time{}, bytes.NewReader(payload))
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "file.bin")
	if err := Download(srv.URL, dest, int64(len(payload)), sum(payload)); err != nil {
		t.Fatalf("Download: %v", err)
	}
	got, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("dest missing: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Fatalf("dest is %d bytes, want %d", len(got), len(payload))
	}
	if len(ranges) != parallelStreams {
		t.Errorf("made %d requests, want %d", len(ranges), parallelStreams)
	}
	if n := PartBytes(dest); n != 0 {
		t.Errorf("%d bytes of partial files left behind, want 0", n)
	}
}

// The point of segment files: an interrupted parallel download resumes instead
// of re-fetching what is already on disk.
func TestDownloadParallelResumes(t *testing.T) {
	payload := bytes.Repeat([]byte("camne"), 480) // 2400, 300 per segment
	withSmallParallelMin(t, 100)

	var mu sync.Mutex
	var ranges []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		ranges = append(ranges, r.Header.Get("Range"))
		mu.Unlock()
		http.ServeContent(w, r, "f", time.Time{}, bytes.NewReader(payload))
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "file.bin")
	// Segment 0 whole, segment 1 half done, segment 7 junk that is too long.
	if err := os.WriteFile(segPath(dest, 0), payload[0:300], 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(segPath(dest, 1), payload[300:450], 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(segPath(dest, 7), bytes.Repeat([]byte("x"), 999), 0o644); err != nil {
		t.Fatal(err)
	}

	if err := Download(srv.URL, dest, int64(len(payload)), sum(payload)); err != nil {
		t.Fatalf("Download: %v", err)
	}
	got, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("dest missing: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Fatalf("dest content wrong: %d bytes, want %d", len(got), len(payload))
	}
	mu.Lock()
	defer mu.Unlock()
	// The whole segment must not have been asked for again, and the half-done
	// one must have resumed at its own offset rather than at its start.
	for _, r := range ranges {
		if r == "bytes=0-299" {
			t.Error("re-fetched a segment that was already complete")
		}
	}
	var sawResume bool
	for _, r := range ranges {
		if r == "bytes=450-599" {
			sawResume = true
		}
	}
	if !sawResume {
		t.Errorf("half-done segment did not resume at its offset; ranges seen: %v", ranges)
	}
}

// A server that answers a range request with the whole file cannot be split
// across connections. Falling back must still produce the right file and leave
// no segments behind.
func TestDownloadParallelFallsBackWhenRangeIgnored(t *testing.T) {
	payload := bytes.Repeat([]byte("camne"), 480)
	withSmallParallelMin(t, 100)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write(payload) // 200 OK, whole body, Range ignored
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "file.bin")
	if err := Download(srv.URL, dest, int64(len(payload)), sum(payload)); err != nil {
		t.Fatalf("Download: %v", err)
	}
	got, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("dest missing: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Errorf("dest content wrong: %d bytes, want %d", len(got), len(payload))
	}
	if n := PartBytes(dest); n != 0 {
		t.Errorf("%d bytes of partial files left behind, want 0", n)
	}
}

// A server that answers a range request with MORE than the range must not be
// able to push one segment's bytes over the next segment's.
func TestDownloadParallelBoundsOverlongResponses(t *testing.T) {
	payload := bytes.Repeat([]byte("camne"), 480)
	withSmallParallelMin(t, 100)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var lo, hi int
		fmt.Sscanf(r.Header.Get("Range"), "bytes=%d-%d", &lo, &hi)
		w.Header().Set("Content-Range", fmt.Sprintf("bytes %d-%d/%d", lo, hi, len(payload)))
		w.WriteHeader(http.StatusPartialContent)
		w.Write(payload[lo:]) // everything from lo, ignoring hi
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "file.bin")
	if err := Download(srv.URL, dest, int64(len(payload)), sum(payload)); err != nil {
		t.Fatalf("Download: %v", err)
	}
	got, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("dest missing: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Errorf("dest is %d bytes, want %d — segments overran their spans", len(got), len(payload))
	}
}

func TestPartBytesCountsEverySegment(t *testing.T) {
	dest := filepath.Join(t.TempDir(), "file.bin")
	if n := PartBytes(dest); n != 0 {
		t.Errorf("PartBytes on nothing = %d, want 0", n)
	}
	for i := 0; i < 3; i++ {
		if err := os.WriteFile(segPath(dest, i), make([]byte, 10), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(dest+".part", make([]byte, 5), 0o644); err != nil {
		t.Fatal(err)
	}
	// Segments and the joined file both count: the progress display must not
	// dip while one is being turned into the other.
	if n := PartBytes(dest); n != 35 {
		t.Errorf("PartBytes = %d, want 35", n)
	}
}

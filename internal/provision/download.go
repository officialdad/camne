package provision

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"sync"
)

// parallelStreams is how many ranged requests share a download.
//
// Measured against the pinned model, three alternating rounds on one link:
// one stream moved 986 MB in 58.8s / 67.8s / 58.8s, eight streams in
// 14.4s / 47.1s / 15.8s — a median of 15.8s against 58.8s, and every parallel
// run beat every single-stream run. The limit is per-connection, not
// bandwidth: the same file reaches 62-68 MB/s split eight ways and 15-17 MB/s
// whole. Hugging Face reconstructs Xet-backed files server-side for clients
// that speak plain HTTP, which is every client camne has.
const parallelStreams = 8

// parallelMin is the size below which one stream is simply better: eight
// connections cost eight TLS handshakes, and the llama-server archive is
// 17 MB. A var, not a const, so the tests can exercise the split path without
// moving 64 MB around.
var parallelMin int64 = 64 << 20

// errNoRange means the server sent the whole file instead of the range asked
// for, so the download cannot be split. Not a user-facing error: Download
// catches it and falls back to a single stream.
var errNoRange = errors.New("server ignored the Range request")

// Download fetches url into dest, whose length must be size bytes. Pass 0 for
// size when the length is not known ahead of time; the download then takes the
// single-stream path, which needs no length.
//
// Large downloads are split into parallelStreams ranged requests, each with
// its own .partN file, joined once every part is whole. Small ones, and
// servers that ignore Range, take a single stream. Either way it verifies the
// sha256 of the complete file BEFORE the atomic rename — never after — and
// deletes the partial file on a failed verification, so nothing corrupted can
// ever sit at dest.
//
// On a student's connection a 1 GB download WILL be interrupted; every partial
// file stays on disk so the next run resumes it rather than starting again.
func Download(url, dest string, size int64, wantSHA256 string) error {
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return fmt.Errorf("could not create camne's download folder — check you have free space in your home folder, then try again: %w", err)
	}
	part := dest + ".part"

	if size >= parallelMin {
		err := downloadSegments(url, dest, size)
		if err == nil {
			if err := joinSegments(dest, parallelStreams); err != nil {
				return err
			}
			return verifyAndRename(part, dest, wantSHA256)
		}
		if !errors.Is(err, errNoRange) {
			return err
		}
		// One stream instead, from scratch: the segments hold ranges this
		// server will not serve, so they are worth nothing now.
		removeSegments(dest, parallelStreams)
	}

	if err := downloadWhole(url, part); err != nil {
		return err
	}
	return verifyAndRename(part, dest, wantSHA256)
}

// segPath names the file holding segment i. The suffix carries a digit so a
// glob for the segments never picks up the joined .part file.
func segPath(dest string, i int) string { return dest + ".part" + strconv.Itoa(i) }

// PartBytes reports how many bytes of dest are on disk across every partial
// file, whichever path the download took. The progress display polls this: it
// is the one number that means the same thing for a single stream, for eight
// segments, and while they are being joined.
func PartBytes(dest string) int64 {
	names, _ := filepath.Glob(dest + ".part*")
	var n int64
	for _, name := range names {
		if fi, err := os.Stat(name); err == nil {
			n += fi.Size()
		}
	}
	return n
}

func removeSegments(dest string, n int) {
	for i := 0; i < n; i++ {
		os.Remove(segPath(dest, i))
	}
}

// downloadSegments fetches every segment concurrently and returns once they
// are all whole. A segment that fails leaves its bytes on disk for the next
// run; only the error comes back.
func downloadSegments(url, dest string, size int64) error {
	span := size / parallelStreams
	var wg sync.WaitGroup
	var mu sync.Mutex
	var firstErr error

	for i := 0; i < parallelStreams; i++ {
		lo := int64(i) * span
		hi := lo + span - 1
		if i == parallelStreams-1 {
			hi = size - 1 // the last segment carries the remainder
		}
		wg.Add(1)
		go func(i int, lo, hi int64) {
			defer wg.Done()
			if err := downloadSegment(url, segPath(dest, i), lo, hi); err != nil {
				mu.Lock()
				if firstErr == nil {
					firstErr = err
				}
				mu.Unlock()
			}
		}(i, lo, hi)
	}
	wg.Wait()
	return firstErr
}

// downloadSegment fills path with url's bytes [lo,hi], resuming whatever is
// already there. A segment longer than its span is junk from an interrupted
// run under different settings, so it is thrown away rather than trusted.
func downloadSegment(url, path string, lo, hi int64) error {
	want := hi - lo + 1
	var have int64
	if fi, err := os.Stat(path); err == nil {
		have = fi.Size()
		if have > want {
			os.Remove(path)
			have = 0
		}
	}
	if have == want {
		return nil // already whole from an earlier run
	}

	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return fmt.Errorf("camne's download address is not valid — please report this at https://github.com/officialdad/camne/issues: %w", err)
	}
	req.Header.Set("Range", "bytes="+strconv.FormatInt(lo+have, 10)+"-"+strconv.FormatInt(hi, 10))
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("download failed — check your internet connection and try again: %w", err)
	}
	defer resp.Body.Close()

	switch resp.StatusCode {
	case http.StatusPartialContent:
	case http.StatusOK:
		return errNoRange
	case http.StatusRequestedRangeNotSatisfiable:
		return nil // nothing left of this segment to ask for
	default:
		return fmt.Errorf("download failed (HTTP %d) — the server is having trouble, try again in a few minutes", resp.StatusCode)
	}

	f, err := os.OpenFile(path, os.O_WRONLY|os.O_APPEND|os.O_CREATE, 0o644)
	if err != nil {
		return fmt.Errorf("could not write the file being downloaded — check you have free space on your disk, then try again: %w", err)
	}
	// Bounded by the span, never by what the server chooses to send: a server
	// answering a range request with more than the range must not be able to
	// push one segment over another's bytes.
	_, copyErr := io.Copy(f, io.LimitReader(resp.Body, want-have))
	closeErr := f.Close()
	if copyErr != nil {
		return fmt.Errorf("the download was cut off — run camne again and it will carry on from where it stopped: %w", copyErr)
	}
	if closeErr != nil {
		return fmt.Errorf("could not save the downloaded file — check you have free space on your disk, then try again: %w", closeErr)
	}
	return nil
}

// joinSegments concatenates the segments into dest+".part" in order, deleting
// each one as it lands so the peak disk cost is the file plus one segment,
// not the file twice.
func joinSegments(dest string, n int) error {
	part := dest + ".part"
	f, err := os.Create(part)
	if err != nil {
		return fmt.Errorf("could not write the file being downloaded — check you have free space on your disk, then try again: %w", err)
	}
	for i := 0; i < n; i++ {
		s, err := os.Open(segPath(dest, i))
		if err != nil {
			f.Close()
			return fmt.Errorf("could not read the downloaded file back — run camne again to download a fresh copy: %w", err)
		}
		_, copyErr := io.Copy(f, s)
		s.Close()
		if copyErr != nil {
			f.Close()
			return fmt.Errorf("could not save the downloaded file — check you have free space on your disk, then try again: %w", copyErr)
		}
		os.Remove(segPath(dest, i))
	}
	if err := f.Close(); err != nil {
		return fmt.Errorf("could not save the downloaded file — check you have free space on your disk, then try again: %w", err)
	}
	return nil
}

// downloadWhole streams the entire file into part on one connection, resuming
// an interrupted part with a Range request. This is the path for small files
// and for servers that will not serve ranges.
func downloadWhole(url, part string) error {
	var offset int64
	if fi, err := os.Stat(part); err == nil {
		offset = fi.Size()
	}

	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return fmt.Errorf("camne's download address is not valid — please report this at https://github.com/officialdad/camne/issues: %w", err)
	}
	if offset > 0 {
		req.Header.Set("Range", "bytes="+strconv.FormatInt(offset, 10)+"-")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("download failed — check your internet connection and try again: %w", err)
	}
	defer resp.Body.Close()

	var f *os.File
	switch resp.StatusCode {
	case http.StatusPartialContent:
		f, err = os.OpenFile(part, os.O_WRONLY|os.O_APPEND, 0o644)
	case http.StatusOK:
		// Fresh download, or the server ignored our Range: start over.
		f, err = os.Create(part)
	case http.StatusRequestedRangeNotSatisfiable:
		// .part is already the full file (or junk). Verify decides which.
		return nil
	default:
		return fmt.Errorf("download failed (HTTP %d) — the server is having trouble, try again in a few minutes", resp.StatusCode)
	}
	if err != nil {
		return fmt.Errorf("could not write the file being downloaded — check you have free space on your disk, then try again: %w", err)
	}

	_, copyErr := io.Copy(f, resp.Body)
	closeErr := f.Close()
	if copyErr != nil {
		// Keep the .part: the next run resumes from here.
		return fmt.Errorf("the download was cut off — run camne again and it will carry on from where it stopped: %w", copyErr)
	}
	if closeErr != nil {
		return fmt.Errorf("could not save the downloaded file — check you have free space on your disk, then try again: %w", closeErr)
	}
	return nil
}

// verifyAndRename hashes the complete .part and only then renames it to dest.
// The whole file is re-read from disk because a resumed download never saw
// the earlier bytes in-stream — one code path, no trust in prior runs.
func verifyAndRename(part, dest, wantSHA256 string) error {
	f, err := os.Open(part)
	if err != nil {
		return fmt.Errorf("could not read the downloaded file back — run camne again to download a fresh copy: %w", err)
	}
	h := sha256.New()
	_, err = io.Copy(h, f)
	f.Close()
	if err != nil {
		return fmt.Errorf("could not read the downloaded file back — run camne again to download a fresh copy: %w", err)
	}
	if got := hex.EncodeToString(h.Sum(nil)); got != wantSHA256 {
		os.Remove(part)
		return fmt.Errorf("the download is damaged (checksum does not match) — the bad file has been deleted, run camne again to download a fresh copy")
	}
	if err := os.Rename(part, dest); err != nil {
		return fmt.Errorf("the download finished but could not be moved into place — check you have free space on your disk, then try again: %w", err)
	}
	return nil
}

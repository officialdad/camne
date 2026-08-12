package provision

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
)

// Download fetches url into dest. It streams into dest+".part", resumes an
// interrupted .part with a Range request, verifies the sha256 of the complete
// file BEFORE the atomic rename — never after — and deletes the partial file
// on a failed verification, so nothing corrupted can ever sit at dest.
//
// On a student's connection a 1 GB download WILL be interrupted; an
// interrupted copy leaves the .part in place so the next run resumes it.
func Download(url, dest, wantSHA256 string) error {
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return fmt.Errorf("tak boleh buat folder cache: %w", err)
	}
	part := dest + ".part"

	var offset int64
	if fi, err := os.Stat(part); err == nil {
		offset = fi.Size()
	}

	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return fmt.Errorf("URL download tak sah: %w", err)
	}
	if offset > 0 {
		req.Header.Set("Range", "bytes="+strconv.FormatInt(offset, 10)+"-")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("download gagal — semak sambungan internet, lepas tu cuba lagi: %w", err)
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
		return verifyAndRename(part, dest, wantSHA256)
	default:
		return fmt.Errorf("download gagal (HTTP %d) — cuba lagi sekejap nanti", resp.StatusCode)
	}
	if err != nil {
		return fmt.Errorf("tak boleh tulis fail download: %w", err)
	}

	_, copyErr := io.Copy(f, resp.Body)
	closeErr := f.Close()
	if copyErr != nil {
		// Keep the .part: the next run resumes from here.
		return fmt.Errorf("download terputus — jalankan semula, camne akan sambung dari mana ia berhenti: %w", copyErr)
	}
	if closeErr != nil {
		return fmt.Errorf("tak boleh simpan fail download: %w", closeErr)
	}
	return verifyAndRename(part, dest, wantSHA256)
}

// verifyAndRename hashes the complete .part and only then renames it to dest.
// The whole file is re-read from disk because a resumed download never saw
// the earlier bytes in-stream — one code path, no trust in prior runs.
func verifyAndRename(part, dest, wantSHA256 string) error {
	f, err := os.Open(part)
	if err != nil {
		return fmt.Errorf("tak boleh baca fail download: %w", err)
	}
	h := sha256.New()
	_, err = io.Copy(h, f)
	f.Close()
	if err != nil {
		return fmt.Errorf("tak boleh baca fail download: %w", err)
	}
	if got := hex.EncodeToString(h.Sum(nil)); got != wantSHA256 {
		os.Remove(part)
		return fmt.Errorf("download rosak (checksum tak sepadan) — fail dah dibuang, cuba download semula")
	}
	if err := os.Rename(part, dest); err != nil {
		return fmt.Errorf("tak boleh simpan fail yang dah siap: %w", err)
	}
	return nil
}

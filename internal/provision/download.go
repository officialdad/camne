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
		return fmt.Errorf("could not create camne's download folder — check you have free space in your home folder, then try again: %w", err)
	}
	part := dest + ".part"

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
		return verifyAndRename(part, dest, wantSHA256)
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
	return verifyAndRename(part, dest, wantSHA256)
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

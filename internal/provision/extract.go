package provision

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"
)

// ExtractZip and ExtractTarGz unpack only the entries keep accepts (given the
// slash-separated entry name) into destDir, preserving relative paths and
// file modes. Archive contents are a trust boundary even after the sha256
// check: entry names that are absolute or escape destDir via ".." are
// rejected, as are tar symlinks whose target would land outside destDir.

// ExtractZip extracts from a .zip archive (llama.cpp Windows builds).
func ExtractZip(archive, destDir string, keep func(name string) bool) error {
	r, err := zip.OpenReader(archive)
	if err != nil {
		return fmt.Errorf("the downloaded file is damaged and will not open — run camne again to download a fresh copy: %w", err)
	}
	defer r.Close()
	for _, f := range r.File {
		if f.FileInfo().IsDir() || !keep(f.Name) {
			continue
		}
		dst, err := safeJoin(destDir, f.Name)
		if err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return fmt.Errorf("the downloaded file is damaged — run camne again to download a fresh copy: %w", err)
		}
		err = writeFile(dst, rc, f.Mode())
		rc.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

// ExtractTarGz extracts from a .tar.gz archive (llama.cpp Linux and macOS
// builds). Symlinks are preserved: the .so SONAME chains beside llama-server
// (libllama.so -> libllama.so.0 -> ...) are how the loader finds them.
func ExtractTarGz(archive, destDir string, keep func(name string) bool) error {
	f, err := os.Open(archive)
	if err != nil {
		return fmt.Errorf("the downloaded file is damaged and will not open — run camne again to download a fresh copy: %w", err)
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return fmt.Errorf("the downloaded file is damaged and will not open — run camne again to download a fresh copy: %w", err)
	}
	defer gz.Close()
	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return fmt.Errorf("the downloaded file is damaged — run camne again to download a fresh copy: %w", err)
		}
		if !keep(hdr.Name) {
			continue
		}
		switch hdr.Typeflag {
		case tar.TypeReg:
			dst, err := safeJoin(destDir, hdr.Name)
			if err != nil {
				return err
			}
			if err := writeFile(dst, tr, hdr.FileInfo().Mode().Perm()); err != nil {
				return err
			}
		case tar.TypeSymlink:
			dst, err := safeJoin(destDir, hdr.Name)
			if err != nil {
				return err
			}
			// The link target, resolved relative to the entry's own
			// directory, must also stay inside destDir.
			target := path.Join(path.Dir(hdr.Name), hdr.Linkname)
			if path.IsAbs(hdr.Linkname) {
				target = hdr.Linkname
			}
			if _, err := safeJoin(destDir, target); err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
				return fmt.Errorf("could not unpack the download — check you have free space on your disk, then try again: %w", err)
			}
			os.Remove(dst) // re-extraction over an old link
			if err := os.Symlink(hdr.Linkname, dst); err != nil {
				return fmt.Errorf("could not unpack the download — check you have free space on your disk, then try again: %w", err)
			}
		}
		// Directories are created as needed by writeFile; other types
		// (devices, fifos) have no business in a release archive — skip.
	}
}

// safeJoin validates an archive entry name and joins it under destDir.
// This is the path-traversal gate: absolute names and names escaping via
// ".." are rejected outright.
func safeJoin(destDir, name string) (string, error) {
	local := filepath.FromSlash(name)
	if strings.Contains(name, `\`) || !filepath.IsLocal(local) {
		return "", fmt.Errorf("the downloaded file contains an unsafe file name (%q), so nothing was unpacked — run camne again to download a fresh copy", name)
	}
	return filepath.Join(destDir, local), nil
}

func writeFile(dst string, src io.Reader, mode os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return fmt.Errorf("could not unpack the download — check you have free space on your disk, then try again: %w", err)
	}
	f, err := os.OpenFile(dst, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, mode)
	if err != nil {
		return fmt.Errorf("could not unpack the download — check you have free space on your disk, then try again: %w", err)
	}
	_, copyErr := io.Copy(f, src)
	closeErr := f.Close()
	if copyErr != nil {
		return fmt.Errorf("could not unpack the download — check you have free space on your disk, then try again: %w", copyErr)
	}
	if closeErr != nil {
		return fmt.Errorf("could not unpack the download — check you have free space on your disk, then try again: %w", closeErr)
	}
	return nil
}

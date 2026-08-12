package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/officialdad/camne/internal/provision"
)

// ensureProvisioned downloads whatever Status says is missing, after exactly
// ONE consent prompt stating the total size in MB. Anything but an explicit
// yes downloads nothing (constraint: no surprise network use, ever).
func ensureProvisioned(st provision.Status) bool {
	asset, err := provision.LlamaAsset(runtime.GOOS, runtime.GOARCH)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return false
	}
	var total int64
	if !st.ServerOK {
		total += asset.Size
	}
	if !st.ModelOK {
		total += provision.ModelSize
	}
	fmt.Fprintf(os.Stderr, "camne perlu download %d MB dulu (sekali je — lepas ni semua jalan offline):\n", total/1_000_000)
	if !st.ServerOK {
		fmt.Fprintf(os.Stderr, "  llama-server  %d MB\n", asset.Size/1_000_000)
	}
	if !st.ModelOK {
		fmt.Fprintf(os.Stderr, "  model         %d MB\n", provision.ModelSize/1_000_000)
	}
	if st.LibcNote != "" {
		fmt.Fprintln(os.Stderr, "Perhatian: "+st.LibcNote)
	}
	fmt.Fprint(os.Stderr, "Nak teruskan? [y/T] ")
	if !askConsent(os.Stdin) {
		fmt.Fprintln(os.Stderr, "Okey, takde apa yang di-download. Bila dah sedia, taip je soalan tadi semula.")
		return false
	}
	if !st.ServerOK {
		if err := installServer(asset, st.ServerPath); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return false
		}
	}
	if !st.ModelOK {
		fmt.Fprintln(os.Stderr, "Download model...")
		if err := withProgress(st.ModelPath+".part", provision.ModelSize, func() error {
			return provision.Download(provision.ModelURL, st.ModelPath, provision.ModelSHA256)
		}); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return false
		}
	}
	fmt.Fprintln(os.Stderr, "Siap — semua dah lengkap.")
	return true
}

// askConsent reads one line; anything but an explicit yes is a no.
func askConsent(r io.Reader) bool {
	sc := bufio.NewScanner(r)
	if !sc.Scan() {
		return false
	}
	switch strings.ToLower(strings.TrimSpace(sc.Text())) {
	case "y", "ya", "yes", "ok", "okey":
		return true
	}
	return false
}

// installServer downloads the pinned llama.cpp release archive (verified
// against its sha256 inside provision.Download, before anything is unpacked)
// and extracts llama-server so the binary lands exactly at serverPath.
func installServer(asset provision.Asset, serverPath string) error {
	cacheDir, err := provision.Dir()
	if err != nil {
		return err
	}
	archive := filepath.Join(cacheDir, "downloads", asset.Name)
	fmt.Fprintln(os.Stderr, "Download llama-server...")
	if err := withProgress(archive+".part", asset.Size, func() error {
		return provision.Download(asset.URL(), archive, asset.SHA256)
	}); err != nil {
		return err
	}
	// Keep only the server binary and the shared libraries it loads from its
	// own directory (the release binaries carry RUNPATH=$ORIGIN).
	keep := func(name string) bool {
		base := path.Base(name)
		return base == filepath.Base(serverPath) ||
			strings.Contains(base, ".so") ||
			strings.HasSuffix(base, ".dylib") ||
			strings.HasSuffix(base, ".dll")
	}
	if strings.HasSuffix(asset.Name, ".zip") {
		// Windows zips are flat: entries land straight in the versioned dir.
		err = provision.ExtractZip(archive, filepath.Dir(serverPath), keep)
	} else {
		// The tar.gz entries are prefixed "llama-<build>/" — the versioned
		// directory name in ServerPath — so extraction goes one level up.
		err = provision.ExtractTarGz(archive, filepath.Dir(filepath.Dir(serverPath)), keep)
	}
	if err != nil {
		return err
	}
	os.Remove(archive)
	// The layout assumption above is upstream's packaging, not ours: verify.
	if _, err := os.Stat(serverPath); err != nil {
		return fmt.Errorf("unpack siap tapi llama-server tak jumpa kat tempat sepatutnya — padam folder %s lepas tu cuba lagi", filepath.Dir(serverPath))
	}
	return nil
}

// withProgress runs dl while a ticker prints how many MB of the .part file
// are on disk so a 1 GB download is never a silent stall.
// ponytail: polls the .part size instead of instrumenting Download — coarse
// (500 ms) but shows resumed downloads correctly; a progress callback on
// provision.Download is the upgrade path.
func withProgress(partPath string, total int64, dl func() error) error {
	done := make(chan struct{})
	go func() {
		t := time.NewTicker(500 * time.Millisecond)
		defer t.Stop()
		for {
			select {
			case <-done:
				return
			case <-t.C:
				if fi, err := os.Stat(partPath); err == nil {
					fmt.Fprintf(os.Stderr, "\r  %d/%d MB", fi.Size()/1_000_000, total/1_000_000)
				}
			}
		}
	}()
	err := dl()
	close(done)
	fmt.Fprintln(os.Stderr)
	return err
}

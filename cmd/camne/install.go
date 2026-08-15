package main

import (
	"fmt"
	"os"
	"path"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/officialdad/camne/internal/provision"
)

// ensureProvisioned downloads whatever Status says is missing. Announced, not
// asked: the size breakdown below and the MB ticker during the fetch mean no
// surprise network use, but nothing is gated — without these two files camne
// cannot answer a single question, so there is no second choice to offer.
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
	fmt.Fprintf(os.Stderr, "camne is setting itself up — downloading %d MB (once only; after this it all works offline):\n", total/1_000_000)
	if !st.ServerOK {
		fmt.Fprintf(os.Stderr, "  llama-server  %d MB\n", asset.Size/1_000_000)
	}
	if !st.ModelOK {
		fmt.Fprintf(os.Stderr, "  model         %d MB\n", provision.ModelSize/1_000_000)
	}
	if st.LibcNote != "" {
		fmt.Fprintln(os.Stderr, "Heads up: "+st.LibcNote)
	}
	if !st.ServerOK {
		if err := installServer(asset, st.ServerPath); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return false
		}
	}
	if !st.ModelOK {
		fmt.Fprintln(os.Stderr, "Downloading the model...")
		if err := withProgress(st.ModelPath+".part", provision.ModelSize, func() error {
			return provision.Download(provision.ModelURL, st.ModelPath, provision.ModelSHA256)
		}); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return false
		}
	}
	fmt.Fprintln(os.Stderr, "Done — everything is ready.")
	return true
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
	fmt.Fprintln(os.Stderr, "Downloading llama-server...")
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
		return fmt.Errorf("unpacking finished but llama-server is not where it should be — delete the folder %s, then run camne again", filepath.Dir(serverPath))
	}
	return nil
}

// withProgress runs dl while a ticker prints how much of the .part file is on
// disk, how fast it is arriving, and how long is left, so a 1 GB download is
// never a silent stall. The speed is what makes a stalled download look
// different from a slow one; the byte counter alone cannot show that, and a
// download that looks hung gets killed and restarted.
//
// Nothing is drawn when stderr is not a terminal: the line rewrites itself with
// \r, which is noise in a redirected log.
//
// ponytail: polls the .part size instead of instrumenting Download — coarse
// (500 ms) but shows resumed downloads correctly; a progress callback on
// provision.Download is the upgrade path.
func withProgress(partPath string, total int64, dl func() error) error {
	if !isTTY(os.Stderr) {
		return dl()
	}
	done := make(chan struct{})
	go func() {
		t := time.NewTicker(500 * time.Millisecond)
		defer t.Stop()
		prev, last := int64(-1), time.Now()
		rate := -1.0 // negative until there are two samples to compare
		for {
			select {
			case <-done:
				return
			case now := <-t.C:
				fi, err := os.Stat(partPath)
				if err != nil {
					continue // not created yet, or already renamed into place
				}
				got := fi.Size()
				if secs := now.Sub(last).Seconds(); prev >= 0 && secs > 0 {
					rate = smoothRate(rate, float64(got-prev)/secs)
				}
				prev, last = got, now
				// Left-padded: the line shrinks when the estimate drops off the
				// end, and \r alone would leave the old tail on screen.
				fmt.Fprintf(os.Stderr, "\r%-70s", progressLine(got, total, rate))
			}
		}
	}()
	err := dl()
	close(done)
	fmt.Fprintln(os.Stderr)
	return err
}

// barWidth is in characters, chosen to leave the whole progress line inside 70
// columns — the narrowest terminal worth designing for.
const barWidth = 24

// smoothRate folds one speed sample into an exponential moving average.
// A negative prev means nothing has been measured yet, so the first sample is
// taken whole rather than averaged against a number that does not exist.
//
// Smoothing is what keeps the line honest in both directions: raw 500 ms
// samples swing wildly with TCP windowing, so every pause would read as a stall
// and every burst as a miracle. It also decays rather than snapping, so a real
// stall visibly falls towards zero over a few seconds instead of flickering.
func smoothRate(prev, sample float64) float64 {
	if prev < 0 {
		return sample
	}
	return 0.7*prev + 0.3*sample
}

// progressLine renders one progress line: bar, megabytes, speed, estimate.
// rate is bytes per second, or negative when nothing has been measured yet.
//
// A measured rate of zero prints as "0.0 MB/s" with no estimate rather than
// being hidden. That is the whole point of showing a speed: a download that has
// stopped must not look like one that is merely slow.
func progressLine(got, total int64, rate float64) string {
	if total <= 0 {
		return fmt.Sprintf("  %d MB", got/1_000_000)
	}
	if got > total {
		got = total // a resumed .part can briefly overshoot a stale total
	}
	filled := int(got * barWidth / total)
	line := fmt.Sprintf("  [%s%s] %3d%%  %d/%d MB",
		strings.Repeat("#", filled), strings.Repeat(".", barWidth-filled),
		got*100/total, got/1_000_000, total/1_000_000)
	if rate < 0 {
		return line
	}
	line += fmt.Sprintf("  %.1f MB/s", rate/1_000_000)
	// No estimate on the last frame: "0s left" under a full bar is noise.
	if rate > 0 && got < total {
		line += "  " + eta(float64(total-got)/rate)
	}
	return line
}

// eta phrases the seconds left for someone watching a download rather than
// timing one. Anything past an hour is said in words: at that point the number
// is a guess about a stalled connection, and printing "417m 12s left" reads as
// a broken program.
func eta(secs float64) string {
	s := int(secs + 0.5)
	switch {
	case s >= 3600:
		return "over an hour left"
	case s >= 60:
		return fmt.Sprintf("%dm %ds left", s/60, s%60)
	case s < 1:
		// The last megabytes, where "0s left" reads as a stuck clock.
		return "almost done"
	}
	return fmt.Sprintf("%ds left", s)
}

// Package provision is the zero-setup subsystem: it knows
// where camne's cache lives, which pinned llama.cpp build and GGUF model to
// fetch for this machine, and how to download, verify, and unpack them.
// Everything is verified against a pinned sha256 BEFORE it is unpacked,
// renamed, or executed. Nothing in this package executes anything.
package provision

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// Pinned llama.cpp release tag. A new upstream build can change behaviour
// without warning, so camne never tracks "latest".
const llamaBuild = "b10333"

// The BM model: Qwen2.5-Coder-1.5B-Instruct tuned on the four-register pool
// (RESULTS.md carries the numbers and the caveat). Swapping the model means
// changing these three consts and nothing else.
const (
	ModelFile   = "camne-1.5b-Q4_K_M.gguf"
	ModelURL    = "https://huggingface.co/opariffazman/camne-1.5b-Q4_K_M/resolve/main/" + ModelFile
	ModelSHA256 = "7576c375d1adf47abb382bfbee6b196511aa7563ec3ebc49506b4ae859e2ba67"
	// ModelSize is the exact GGUF byte size, from the Hugging Face LFS
	// metadata for the pinned revision.
	ModelSize int64 = 986048000
)

// Asset is one llama.cpp release file for a specific platform.
type Asset struct {
	Name   string // release asset file name
	SHA256 string
	Size   int64
}

// URL is the direct release-asset download URL for the pinned build.
func (a Asset) URL() string {
	return "https://github.com/ggml-org/llama.cpp/releases/download/" + llamaBuild + "/" + a.Name
}

// llamaAssets maps GOOS/GOARCH to the release asset for the pinned build.
// Digests and sizes come from the GitHub release API for that tag, hardcoded
// so provisioning never depends on the rate-limited API at runtime.
var llamaAssets = map[string]Asset{
	"linux/amd64":   {"llama-" + llamaBuild + "-bin-ubuntu-x64.tar.gz", "936ce04d98abe2a977e9dd2ff92659bb96947e136acee8f2bc3e21d8eaebbf23", 16507165},
	"linux/arm64":   {"llama-" + llamaBuild + "-bin-ubuntu-arm64.tar.gz", "95da1a0f7538340f625b0301593ee63c046ec0a155c74f21444ea4d43bca79a1", 13377770},
	"darwin/amd64":  {"llama-" + llamaBuild + "-bin-macos-x64.tar.gz", "6ffd9e0b9b2e3ab6ccfba332a74b968b0fef891f01bd4747d3d75bc7393877ea", 11290712},
	"darwin/arm64":  {"llama-" + llamaBuild + "-bin-macos-arm64.tar.gz", "e5d67c5264107e3c14d3bf2aee349365bb2b85ae99bb077a0cb974a1c4c2741a", 11015270},
	"windows/amd64": {"llama-" + llamaBuild + "-bin-win-cpu-x64.zip", "563ab97cd003cf7cd4843677e6fea2f6162aee0c9580589c8d9e5816923076d5", 18399512},
	"windows/arm64": {"llama-" + llamaBuild + "-bin-win-cpu-arm64.zip", "6497bfecd5926f48b816a65a8f8e21e613f822850361ab7bdaf33b0489025235", 12237230},
}

// LlamaAsset picks the llama.cpp release asset for a platform.
func LlamaAsset(goos, goarch string) (Asset, error) {
	a, ok := llamaAssets[goos+"/"+goarch]
	if !ok {
		return Asset{}, fmt.Errorf("camne does not support %s/%s yet — open an issue at https://github.com/officialdad/camne/issues if you need this platform", goos, goarch)
	}
	return a, nil
}

// Dir is camne's cache root: os.UserCacheDir()/camne. Layout:
//
//	bin/llama-<build>/   the unpacked llama.cpp runtime, versioned so an
//	                     upgrade never overwrites a working install
//	models/              GGUF files
func Dir() (string, error) {
	c, err := os.UserCacheDir()
	if err != nil {
		return "", fmt.Errorf("could not find your system's cache folder, so camne has nowhere to keep its files — check that HOME is set, then try again: %w", err)
	}
	return filepath.Join(c, "camne"), nil
}

func serverBinary() string {
	if runtime.GOOS == "windows" {
		return "llama-server.exe"
	}
	return "llama-server"
}

// ServerPath is where the llama-server binary lives once unpacked.
func ServerPath() (string, error) {
	d, err := Dir()
	if err != nil {
		return "", err
	}
	return filepath.Join(d, "bin", "llama-"+llamaBuild, serverBinary()), nil
}

// ModelPath is where the GGUF lives once downloaded.
func ModelPath() (string, error) {
	d, err := Dir()
	if err != nil {
		return "", err
	}
	return filepath.Join(d, "models", ModelFile), nil
}

// sidecarPath names the file that records the digest of the model beside it.
// The identity of a cached model is its digest, not its name: a re-tune of the
// same base ships under the same name at the same byte size, so a name-and-size
// check leaves every existing install on the old weights forever (issue #38).
func sidecarPath(modelPath string) string { return modelPath + ".sha256" }

// ModelState is what the file in the cache actually is.
type ModelState int

const (
	ModelReady      ModelState = iota // the pinned model, digest recorded
	ModelMissing                      // nothing at that path
	ModelDamaged                      // wrong size: truncated, or not the model at all
	ModelUnrecorded                   // right size, no digest recorded (cached before camne kept one)
	ModelStale                        // a digest is recorded and it is not the pinned one
)

// String is printed by `camne doctor`, so it is plain English rather than the
// constant's name: "model: missing" for a file that is visibly on disk is
// exactly the confusing error the user-facing text rules forbid.
func (s ModelState) String() string {
	switch s {
	case ModelReady:
		return "found"
	case ModelDamaged:
		return "damaged"
	case ModelUnrecorded:
		return "unverified"
	case ModelStale:
		return "out of date"
	}
	return "missing"
}

// modelState decides what is on disk without hashing it. The size is a cheap
// pre-filter that catches a truncated file, and the sidecar carries the digest
// that WAS verified — against the whole gigabyte, at download time. Rehashing
// ~1 GB on every run would cost far more than it is worth.
func modelState(path string, size int64, want string) ModelState {
	fi, err := os.Stat(path)
	if err != nil {
		return ModelMissing
	}
	if fi.Size() != size {
		return ModelDamaged
	}
	sum, err := os.ReadFile(sidecarPath(path))
	if err != nil {
		return ModelUnrecorded
	}
	if strings.TrimSpace(string(sum)) != want {
		return ModelStale
	}
	return ModelReady
}

func writeSidecar(modelPath, sum string) error {
	if err := os.WriteFile(sidecarPath(modelPath), []byte(sum+"\n"), 0o644); err != nil {
		return fmt.Errorf("the model is downloaded but its checksum could not be saved — check you have free space on your disk, then try again: %w", err)
	}
	return nil
}

// AdoptModel rescues a model cached before camne recorded digests: hashing the
// file once takes seconds, re-downloading a gigabyte over someone's phone does
// not. It reports whether the bytes on disk ARE the pinned model, recording the
// digest when they are. Anything else — a recorded digest that already
// disagreed, the wrong size, different bytes — is left for the download to fix.
func AdoptModel(path string) bool { return adoptModel(path, ModelSize, ModelSHA256) }

func adoptModel(path string, size int64, want string) bool {
	if modelState(path, size, want) != ModelUnrecorded {
		return false
	}
	if sum, err := hashFile(path); err != nil || sum != want {
		return false
	}
	return writeSidecar(path, want) == nil
}

// DownloadModel fetches the pinned GGUF, records its digest beside it, and only
// then clears out what an earlier model left behind. That order is the point:
// the old weights are what camne answers from until the new ones are verified
// and in place, so a download that dies half way still leaves a working install.
func DownloadModel(dest string) error {
	if err := Download(ModelURL, dest, ModelSize, ModelSHA256); err != nil {
		return err
	}
	if err := writeSidecar(dest, ModelSHA256); err != nil {
		return err
	}
	removeOtherModels(dest)
	return nil
}

// removeOtherModels deletes everything in the models folder that is not the
// current model or its sidecar — otherwise a model that ships under a new name
// strands a gigabyte on disk at every swap.
func removeOtherModels(dest string) {
	names, _ := filepath.Glob(filepath.Join(filepath.Dir(dest), "*"))
	for _, n := range names {
		if n != dest && n != sidecarPath(dest) {
			os.Remove(n)
		}
	}
}

// Status reports what is already provisioned. Used by `camne doctor`.
type Status struct {
	CacheDir   string
	ServerPath string
	ServerOK   bool
	ModelPath  string
	Model      ModelState
	LibcNote   string // non-empty when this Linux libc cannot run the prebuilt
}

// ModelOK reports whether the cached model needs nothing done to it.
func (st Status) ModelOK() bool { return st.Model == ModelReady }

// GetStatus inspects the cache. It changes nothing.
func GetStatus() (Status, error) {
	var st Status
	d, err := Dir()
	if err != nil {
		return st, err
	}
	st.CacheDir = d
	st.ServerPath, _ = ServerPath()
	if fi, err := os.Stat(st.ServerPath); err == nil && !fi.IsDir() {
		st.ServerOK = true
	}
	st.ModelPath, _ = ModelPath()
	st.Model = modelState(st.ModelPath, ModelSize, ModelSHA256)
	st.LibcNote = libcNote()
	return st, nil
}

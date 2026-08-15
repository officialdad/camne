package main

// Self-update. camne notices a newer release and OFFERS it — the binary is
// only replaced after the user answers the prompt (constraint 5).
//
// The check runs after the answer has already been printed, never in front of
// it (constraint 3), at most once per 24 hours, and sends nothing but a plain
// GET of the releases API — no query text, no telemetry (constraint 4).

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/officialdad/camne/internal/provision"
)

const (
	repo          = "officialdad/camne"
	latestAPI     = "https://api.github.com/repos/" + repo + "/releases/latest"
	releaseBase   = "https://github.com/" + repo + "/releases/download/"
	checkInterval = 24 * time.Hour
)

// One shared client so the check can never hang a run: a slow or captive
// network costs 5 s, once a day, after the answer is already on screen.
var updateClient = &http.Client{Timeout: 5 * time.Second}

// offerUpdate is the automatic path, called after every command has finished
// printing. Everything about it is silent on failure — a flaky network must
// never make a normal camne run look broken.
func offerUpdate() {
	// A previous Windows update parked the running binary aside; this is the
	// later run that gets to delete it.
	if runtime.GOOS == "windows" {
		if self, err := os.Executable(); err == nil {
			os.Remove(self + ".old")
		}
	}
	stamp, err := stampPath()
	if err != nil {
		return
	}
	tty := isTTY(os.Stdin) && isTTY(os.Stdout) && isTTY(os.Stderr)
	if !shouldCheck(version, stamp, tty, time.Now()) {
		return
	}
	// Stamp before asking, not after: a GitHub outage must not turn into a
	// request on every single invocation.
	touch(stamp)

	tag, err := latestTag(latestAPI)
	if err != nil || tag == version {
		return
	}
	fmt.Fprintf(os.Stderr, "\nA newer camne is available: %s (you have %s)\n", tag, version)
	fmt.Fprint(os.Stderr, "Update now? [y/N] ")
	var answer string
	fmt.Fscanln(os.Stdin, &answer) // a bare Enter leaves answer empty, which is "no"
	if !strings.EqualFold(strings.TrimSpace(answer), "y") && !strings.EqualFold(strings.TrimSpace(answer), "yes") {
		fmt.Fprintf(os.Stderr, "Ok, staying on %s. Run `camne update` whenever you want it.\n", version)
		return
	}
	if err := selfUpdate(tag); err != nil {
		fmt.Fprintln(os.Stderr, err)
	}
}

// update is `camne update`: same job, no prompt and no throttle. Typing the
// command IS the consent, so there is nothing left to ask.
func update() int {
	if version == "dev" {
		fmt.Fprintln(os.Stderr, "This camne was built locally, so there is no version to compare against.")
		fmt.Fprintln(os.Stderr, "Install a released camne first if you want it to update itself:")
		fmt.Fprintln(os.Stderr, "  curl -fsSL https://raw.githubusercontent.com/"+repo+"/main/install.sh | sh")
		return 1
	}
	tag, err := latestTag(latestAPI)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Could not reach GitHub to check for a newer camne.")
		fmt.Fprintln(os.Stderr, "Check your internet connection and try again.")
		return 1
	}
	if stamp, err := stampPath(); err == nil {
		touch(stamp)
	}
	if tag == version {
		fmt.Println("camne " + version + " is already the newest version.")
		return 0
	}
	if err := selfUpdate(tag); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

// shouldCheck is every skip rule in one place. A locally built binary has no
// meaningful tag to compare, a check inside the last 24 h is enough, and a
// piped camne must behave exactly as it did before — `camne ... | sh` is
// normal usage, and prompting into a pipeline would interleave the prompt with
// the command the shell is running.
func shouldCheck(ver, stamp string, tty bool, now time.Time) bool {
	if ver == "dev" || !tty {
		return false
	}
	fi, err := os.Stat(stamp)
	return err != nil || now.Sub(fi.ModTime()) >= checkInterval
}

// stampPath is the throttle file. There is no format and nothing to parse —
// the mtime is the whole state.
func stampPath() (string, error) {
	d, err := provision.Dir()
	if err != nil {
		return "", err
	}
	return filepath.Join(d, "update-check"), nil
}

func touch(path string) {
	os.MkdirAll(filepath.Dir(path), 0o755)
	if f, err := os.Create(path); err == nil {
		f.Close()
	}
}

// latestTag reads the tag name of the newest release. The URL is an argument
// so tests can point it at an httptest server instead of the network.
func latestTag(apiURL string) (string, error) {
	body, err := fetch(apiURL)
	if err != nil {
		return "", err
	}
	var rel struct {
		TagName string `json:"tag_name"`
	}
	if err := json.Unmarshal(body, &rel); err != nil {
		return "", fmt.Errorf("could not read GitHub's reply: %w", err)
	}
	if rel.TagName == "" {
		return "", fmt.Errorf("GitHub's reply has no release tag in it")
	}
	return rel.TagName, nil
}

// fetch GETs a small text resource. The limit is there because the response is
// untrusted input: a 1 MB cap on a few-KB document.
func fetch(url string) ([]byte, error) {
	resp, err := updateClient.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GitHub answered HTTP %d", resp.StatusCode)
	}
	return io.ReadAll(io.LimitReader(resp.Body, 1<<20))
}

// assetName is the release file for a platform, matching scripts/build.sh
// byte for byte. Change one and the other stops working.
func assetName(goos, goarch string) string {
	n := "camne_" + goos + "_" + goarch
	if goos == "windows" {
		n += ".exe"
	}
	return n
}

// sumFor pulls one asset's sha256 out of a `sha256sum` listing. That hash is
// what provision.Download verifies against, so a missing or wrong line has to
// be an error, never a silently skipped check.
func sumFor(checksums, asset string) (string, error) {
	for _, line := range strings.Split(checksums, "\n") {
		f := strings.Fields(line)
		// "<hash>  name", or "<hash> *name" from sha256sum's binary mode.
		if len(f) == 2 && strings.TrimPrefix(f[1], "*") == asset {
			return f[0], nil
		}
	}
	return "", fmt.Errorf("this release has no %s build (%s is missing from checksums.txt) — download camne by hand from https://github.com/%s/releases", runtime.GOOS+"/"+runtime.GOARCH, asset, repo)
}

// selfUpdate downloads the release binary and puts it where this one is.
//
// The download, the sha256 check and the atomic rename are provision.Download,
// unchanged: it verifies BEFORE the rename and deletes the file on a mismatch,
// so nothing unverified can ever end up at the destination. No verification
// logic is repeated here.
func selfUpdate(tag string) error {
	self, err := os.Executable()
	if err != nil {
		return fmt.Errorf("could not work out where camne is installed, so nothing was changed — reinstall with install.sh instead: %w", err)
	}
	// An installer may have left a symlink; replace what it points at.
	if resolved, err := filepath.EvalSymlinks(self); err == nil {
		self = resolved
	}
	asset := assetName(runtime.GOOS, runtime.GOARCH)
	sums, err := fetch(releaseBase + tag + "/checksums.txt")
	if err != nil {
		return fmt.Errorf("could not download the checksum list for %s, so nothing was changed — try again later: %w", tag, err)
	}
	want, err := sumFor(string(sums), asset)
	if err != nil {
		return err
	}

	fmt.Fprintf(os.Stderr, "Downloading camne %s (%s/%s)...\n", tag, runtime.GOOS, runtime.GOARCH)
	// Download next to the binary being replaced: same filesystem, so the
	// rename below is atomic, and a directory camne cannot write to fails here
	// rather than after a pointless download.
	staged := self + ".new"
	// Size 0: checksums.txt carries no length, and a camne binary is small
	// enough that splitting it across connections would cost more than it saves.
	if err := provision.Download(releaseBase+tag+"/"+asset, staged, 0, want); err != nil {
		return fmt.Errorf("%w\ncamne was not changed. You can also reinstall with install.sh", err)
	}
	if err := os.Chmod(staged, 0o755); err != nil {
		os.Remove(staged)
		return fmt.Errorf("could not make the new camne runnable, so nothing was changed: %w", err)
	}
	fmt.Fprintln(os.Stderr, "Checksum ok.")
	if err := replaceSelf(staged, self); err != nil {
		os.Remove(staged)
		return err
	}
	fmt.Fprintf(os.Stderr, "Done — camne %s.\n", tag)
	return nil
}

// replaceSelf moves staged over the running binary at self.
func replaceSelf(staged, self string) error {
	if runtime.GOOS == "windows" {
		// Windows will not let a running .exe be overwritten, but it will let
		// it be renamed. Park it, move the new one in, and delete the parked
		// copy on a later run (see offerUpdate).
		parked := self + ".old"
		os.Remove(parked)
		if err := os.Rename(self, parked); err != nil {
			return fmt.Errorf("could not move the running camne aside, so nothing was changed — close any other camne windows and try again: %w", err)
		}
		if err := os.Rename(staged, self); err != nil {
			os.Rename(parked, self) // put the working one back
			return fmt.Errorf("could not put the new camne in place, so the old one was restored — try again: %w", err)
		}
		return nil
	}
	if err := os.Rename(staged, self); err != nil {
		return fmt.Errorf("could not replace %s, so nothing was changed — you may need to run this with sudo: %w", self, err)
	}
	return nil
}

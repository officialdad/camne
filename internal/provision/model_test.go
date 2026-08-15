package provision

import (
	"os"
	"path/filepath"
	"testing"
)

// writeModel puts body at models/<name> inside a temp cache and returns the path.
func writeModel(t *testing.T, name, body string) string {
	t.Helper()
	dir := filepath.Join(t.TempDir(), "models")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(dir, name)
	if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestModelState(t *testing.T) {
	const body = "pretend this is a gguf"
	size, want := int64(len(body)), sum([]byte(body))

	tests := []struct {
		name    string
		sidecar string // "" = do not write one
		body    string
		state   ModelState
	}{
		{"matching sidecar", want, body, ModelReady},
		{"trailing newline is fine", want + "\n", body, ModelReady},
		{"no sidecar", "", body, ModelUnrecorded},
		{"stale sidecar", sum([]byte("an older tune")), body, ModelStale},
		{"truncated file", want, body[:5], ModelDamaged},
		{"same size, different bytes, no sidecar", "", "PRETEND THIS IS A GGUF", ModelUnrecorded},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			p := writeModel(t, "model.gguf", tt.body)
			if tt.sidecar != "" {
				if err := os.WriteFile(sidecarPath(p), []byte(tt.sidecar), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			if got := modelState(p, size, want); got != tt.state {
				t.Errorf("got %v (%q), want %v (%q)", got, got, tt.state, tt.state)
			}
		})
	}

	t.Run("missing", func(t *testing.T) {
		p := filepath.Join(t.TempDir(), "nothing.gguf")
		if got := modelState(p, size, want); got != ModelMissing {
			t.Errorf("got %v, want %v", got, ModelMissing)
		}
	})
}

func TestAdoptModel(t *testing.T) {
	const body = "pretend this is a gguf"
	size, want := int64(len(body)), sum([]byte(body))

	t.Run("pre-sidecar install holding the pinned model is adopted once", func(t *testing.T) {
		p := writeModel(t, "model.gguf", body)
		if !adoptModel(p, size, want) {
			t.Fatal("expected the file to be adopted")
		}
		if got := modelState(p, size, want); got != ModelReady {
			t.Errorf("after adopting: got %v, want %v", got, ModelReady)
		}
		// Second call is a no-op: the sidecar now exists.
		if adoptModel(p, size, want) {
			t.Error("adopted twice; the sidecar should have stopped the second call")
		}
	})

	t.Run("different bytes at the same size are not adopted", func(t *testing.T) {
		p := writeModel(t, "model.gguf", "PRETEND THIS IS A GGUF")
		if adoptModel(p, size, want) {
			t.Fatal("adopted a file that is not the pinned model")
		}
		if _, err := os.Stat(sidecarPath(p)); err == nil {
			t.Error("wrote a sidecar for a file that did not match")
		}
	})

	t.Run("a stale sidecar is only fixed by a download", func(t *testing.T) {
		p := writeModel(t, "model.gguf", body)
		if err := os.WriteFile(sidecarPath(p), []byte(sum([]byte("older"))), 0o644); err != nil {
			t.Fatal(err)
		}
		if adoptModel(p, size, want) {
			t.Fatal("adopted over a stale sidecar instead of re-downloading")
		}
	})
}

func TestRemoveOtherModels(t *testing.T) {
	keep := writeModel(t, "camne-r7.gguf", "new")
	if err := writeSidecar(keep, sum([]byte("new"))); err != nil {
		t.Fatal(err)
	}
	dir := filepath.Dir(keep)
	orphans := []string{"camne-r6.gguf", "camne-r6.gguf.sha256", "camne-r7.gguf.part3"}
	for _, name := range orphans {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	removeOtherModels(keep)

	left, err := filepath.Glob(filepath.Join(dir, "*"))
	if err != nil {
		t.Fatal(err)
	}
	if len(left) != 2 {
		t.Fatalf("got %v, want only the model and its sidecar", left)
	}
	for _, p := range []string{keep, sidecarPath(keep)} {
		if _, err := os.Stat(p); err != nil {
			t.Errorf("deleted a file it had to keep: %v", err)
		}
	}
}

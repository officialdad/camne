# Contributing to camne

Read [`CLAUDE.md`](CLAUDE.md) for the working rules and [`PROMPT.md`](PROMPT.md)
for the constraints and architecture rationale. This file is just the commands.

## Build, test, lint

Go, `CGO_ENABLED=0`, **standard library only**. No `cgo` — it breaks the
cross-compilation that is the main reason Go was chosen.

```bash
go build ./...
go test ./...
go vet ./...
gofmt -l .                                              # must print nothing
go run honnef.co/go/tools/cmd/staticcheck@2025.1.1 ./...  # must print nothing
scripts/build.sh                                        # all six targets
cd dataset && python3 test_pipeline.py                  # dataset pipeline
```

CI runs exactly these on every push and PR to `main`. Lint is `go vet` plus
staticcheck — no `golangci-lint`, no `.golangci.yml`. staticcheck is run via
`go run <pkg>@<version>`, so it never enters `go.mod`. Dev tooling is not a
runtime dependency.

Adding a module needs a written justification in the PR.

## The six constraints

A change that violates one of these is wrong; the constraint is not.

1. Colloquial Malay input works (`camne nak buat file baru`), rojak works, English still works.
2. Zero setup — no `pipx`, no Ollama, no separate `llama-server` install, no compiler on the user's machine.
3. Runs on 4 cores / 8 GB / no GPU. Warm answer < 1.5 s, cold start < 5 s, RSS < 2.5 GB.
4. Nothing typed at the prompt leaves the machine. No telemetry.
5. Nothing executes without explicit consent. `BAHAYA` never auto-runs.
6. Linux, macOS, Windows × amd64, arm64.

## Before you open a PR

- Non-trivial logic (a branch, a loop, a parser, anything in the safety or
  download path) leaves one runnable `go test`. Table-driven, no frameworks.
- Touching `internal/safety`? Read the audit notes in `CLAUDE.md` first. Those
  tests *are* the audit — do not weaken them.
- Model or dataset change? Numbers, not examples. See `CLAUDE.md`.
- User-facing text is colloquial Malay with technical terms left in English
  (*file*, *folder*, *server*). Error messages say what to do next. A linter
  does not get to reword them.

## Commits

Conventional commits. Subject in English, imperative, no trailing period.

```
feat: add resident llama-server engine
fix: strip terminal control bytes before printing model output
docs: update README for the working engine
test: port the adversarial safety audit
chore: pin staticcheck in CI
```

Prefixes: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.

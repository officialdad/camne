# CLAUDE.md

`camne` — plain Malay in, shell command out, fully local, zero setup.

## The six constraints

Violating any of these means the change is wrong, not the constraint.

1. Colloquial Malay input works (`camne nak buat file baru`), rojak works, English still works.
2. Zero setup — no `pipx`, no Ollama, no separate `llama-server` install, no compiler on the user's machine.
3. Runs on 4 cores / 8 GB / no GPU. Warm answer < 1.5 s, cold start < 5 s, RSS < 2.5 GB.
4. Nothing typed at the prompt leaves the machine. No telemetry.
5. Nothing executes without explicit consent. camne prints the command and stops there; a command the safety checker flags is still only printed.
6. Linux, macOS, Windows × amd64, arm64.

## Stack

Go, `CGO_ENABLED=0`, **standard library only**.

```bash
go build ./...
go test ./...
CGO_ENABLED=0 GOOS=linux   GOARCH=amd64 go build -o dist/camne       ./cmd/camne
CGO_ENABLED=0 GOOS=darwin  GOARCH=arm64 go build -o dist/camne       ./cmd/camne
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o dist/camne.exe   ./cmd/camne
```

Adding a module requires a written justification in the PR. `cgo` is banned —
it destroys cross-compilation, which is the main reason Go was chosen.

## How to work here

Take the simplest thing that satisfies the constraints:

1. Does this need to exist? Speculative need → skip it, say so in one line.
2. Already in this repo? Reuse it. Look before writing.
3. Standard library does it? Use it.
4. One line? One line.
5. Only then: the minimum code that works.

No interface with one implementation. No factory for one product. No config
knob for a value that never changes. Shortest working diff wins — but only
after you have read the code the change touches and traced the real flow.
The smallest change in the wrong place is a second bug.

Bug reports name symptoms. Grep every caller before editing; one guard in the
shared function beats a guard in each caller and leaves no sibling broken.

Deliberate shortcuts with a known ceiling get a `// ponytail:` comment naming
the ceiling and the upgrade path.

Never simplify away: input validation at trust boundaries, download
verification, the safety checker, error handling that loses user data.

## Non-trivial logic leaves one runnable check

A branch, a loop, a parser, anything in the safety or download path gets the
smallest test that fails if the logic breaks. Plain `go test`, table-driven, no
frameworks. Trivial one-liners need no test.

## Safety code — read first, write second

Before touching `internal/safety`, read the module docstring of
[`whatisit_pkg/whatisit/safety.py`](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/master/whatisit_pkg/whatisit/safety.py).
It records an adversarial audit that found the obvious regex version was
evadable and noisy at once. Do not re-derive those bugs.

Rules that came out of it:

- Strip terminal control bytes. Model output is untrusted and reaches a terminal.
- Tokenize; never regex a raw command string. `rm -rf '/'` == `rm -rf /`.
- Normalize long options to short before matching.
- A target must **be** a critical path, never merely **contain** one.
  `/home` is critical. `/home/ariff/project/build` is not.
- `$VAR` and command substitution are dangerous by default.

It is a seatbelt, not a sandbox. The real protection is that the default path
never executes. Keep it that way.

Port `tests/test_safety.py` before the implementation — those tests are the audit.

## Model work — measure or it did not happen

No model change merges without numbers. Not examples, numbers.

- Accuracy: [InterCode-ALFA](https://github.com/westenfelder/InterCode-ALFA),
  **unmodified scorer**, 300 tasks, colloquial-BM prompts plus the English
  control set.
- Fixed and always stated: temperature 0, `max_tokens=64`, threshold 0.75.
- Significance: paired exact McNemar vs the untuned base, with 95% CI. Report
  when 300 tasks cannot resolve a difference — that is a result too.
- Performance on the target box: tok/s, warm latency, cold start, RSS, disk
  size, install wall time. Sweep threads 2/4/6/8.
- Include the untuned base as a row. A tune that does not beat its own base is
  not a result.
- Seed 42, one variable changed per run.
- Noise floor (issue #57): the same pool and seed reproduce to ≤ 0.013 per
  register and 0 probe prompts, so one seed suffices when the paired CI
  excludes zero. A delta inside ±0.02 is "no difference", not a trend.
  That floor is the **scorer**, not the training (PR #68): ~1% of tasks
  return a different verdict for a byte-identical command, because the task
  itself is not deterministic — `find -mtime/-mmin/-atime` against
  build-time file stamps, unsorted `find -print`, `ps aux`, `dig`, and the
  mtime gzip and tar write into their own headers. Upstream documents none
  of this; assume it is there.

### Scoring hygiene

The scorer and the container are never edited — that is what makes a number
comparable to anyone else's. Everything below controls the *measurement*
around it, which is the same split
[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md)
draws with `--use_cache` and [arXiv 2405.14782](https://arxiv.org/pdf/2405.14782)
argues for.

- Generation and scoring stay separate files, so scoring can be re-run
  without re-generating. Already true: `answers_*.jsonl` → `.scored.jsonl`.
- Cache the verdict on `(index, command)` and reuse it. 61% of our scoring
  calls repeat a command already scored for that task, and re-scoring it is
  where phantom lost/gained pairs come from. A cache makes a comparison
  self-consistent; it does not make a verdict correct.
- Score every arm being compared in one session against one image build.
  `-mtime +31` means something different after a rebuild.
- Known-flaky tasks: score 3×, take the majority. Cheap — it is ~1% of the
  set, not all of it. Identifying them by repeated runs is what the
  execution-benchmark literature does ([arXiv 2505.23419](https://arxiv.org/html/2505.23419v2),
  [arXiv 2310.15642](https://arxiv.org/pdf/2310.15642)); we cannot drop
  them, the 300 are fixed, so report them instead.
- State the embed model digest next to the llama build. `mxbai-embed-large`
  is half the scorer.
- Do not reach for `libfaketime` to pin the container clock. It changes the
  environment and costs roughly 10×; one session per comparison buys the
  same thing.

### The probe and ALFA do not measure the same thing

`training/probe.py` measures whether a task survives rephrasing; ALFA
measures whether the tool was right. Only 17% of the ALFA-BM tasks the
shipped model passes use a beginner tool at all — `find` alone is a third
of them. Runs 10–13 bought probe points and paid ALFA points, one inside-CI
step at a time, until the sum cleared the CI (PR #68). Quote both numbers or
neither, and treat a probe win with an ALFA loss as the trade it is.

## Dataset work

- Commands are **never** translated. Byte-identical to source. This is what
  keeps the scorer usable.
- Four registers per pair: formal BM, colloquial, rojak, English.
- Technical nouns stay English — *file*, *folder*, *delete*, *download*,
  *server*. A translation API will "correct" these and poison the set. Stoplist
  them back.
- Hand-read 200 rows before training on 125k. Reads like a government circular
  → the pipeline is broken.

## User-facing text

English, plain, aimed at someone who has never used a terminal. Error messages
say what to do next. No Go stack traces reaching the user.

Output is English; input is not. Colloquial Malay in, rojak in, English in —
`camne nak buat file baru` still works, camne just answers in English
(issue #25). Do not "fix" a printed string back to Malay.

This covers what the program prints, and only that. Repo docs — README,
CONTRIBUTING, release notes, commits, issues, PRs — are English too, because
their audience is contributors, not the person at the prompt. Malay quoted
inside them (the demo queries, real CLI input) stays verbatim.

## Commits

Conventional commits, written normally (not in the terse style used in chat):
`feat:`, `fix:`, `docs:`, `test:`, `chore:`. Subject in English, imperative.

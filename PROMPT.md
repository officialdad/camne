# camne — project brief

`camne` turns plain Malay into a shell command, on your own machine, with no
setup, no API key, and no network after the first run.

```console
$ camne nak buat file baru
touch nama_fail.txt

$ camne cari file lagi besar dari 100MB kat folder ni
find . -size +100M -exec ls -lh {} \;

$ camne nak padam semua benda dalam root
  !! BAHAYA  padam paksa rekursif pada laluan kritikal
rm -rf /
```

The name is the question people actually type. `camne` is how Malaysians say
*macam mana* — "how do I". The tool answers it.

---

## 1. Why this exists

Every natural-language-to-shell tool assumes you write English. Learning the
command line in Malaysia means translating your own question into a second
language before a tool will help you. That is a tax on exactly the people who
need the help most: beginners.

There is a second problem underneath it. The existing local tools
([shell_gpt](https://github.com/TheR1D/shell_gpt),
[ShellOracle](https://github.com/djcopley/ShellOracle),
[aichat](https://github.com/sigoden/aichat)) are wrappers — you bring your own
model, your own Ollama, your own config. A beginner who cannot yet use `find`
cannot be expected to install a model runtime first. The setup is harder than
the problem.

`camne` fixes both: Malay in, command out, and the first run installs
everything itself.

## 2. Non-negotiables

These are the constraints the design must satisfy. If a decision violates one,
the decision is wrong, not the constraint.

1. **Malay input, colloquial register.** `camne nak buat file baru` must work,
   not just `Bagaimanakah cara untuk mencipta fail baharu`. Rojak
   (Malay/English code-switching) is the normal case, not an edge case. English
   input must keep working too.
2. **Zero-setup.** First run downloads what it needs and starts working. No
   `setup` subcommand the user must know to run, no separate `llama-server`
   install, no Ollama, no Python, no `pipx`, no compiler. One binary, one
   download, done — no question to answer first.
3. **Runs on a small machine.** 4 CPU cores, 8 GB RAM, no GPU, spinning-rust or
   slow SSD. A student laptop. Not a workstation.
4. **Fully local after install.** Nothing typed at the prompt leaves the
   machine. No telemetry.
5. **Never executes without consent.** Default path prints; it does not run.
   Anything flagged `BAHAYA` is never auto-run at all.
6. **Cross-platform.** Linux, macOS, Windows. amd64 and arm64.

## 3. Target machine, stated as numbers

Every benchmark in this project is measured against this box, or worse:

| | |
|---|---|
| CPU | 4 cores, no AVX-512 assumed |
| RAM | 8 GB total, so the tool gets ~2 GB |
| GPU | none |
| Disk | assume the model download is the slowest part of install |

Budget: **warm answer under 1.5 s**, **cold start under 5 s**, **resident RSS
under 2.5 GB**. A design that only meets these on a 16-core desktop has failed.

## 4. Architecture

### 4.1 Language: Go, `CGO_ENABLED=0`, standard library only

Rationale, in order of weight:

- **Kills the runtime dependency.** The prior art (`whatisit`) is a Python
  package and inherits the whole `pip`/`pipx`/externally-managed-environment
  problem. A Go binary has no runtime. `curl` one file and it runs.
- **Cross-compiles from one machine.** `GOOS`/`GOARCH` produces all six targets
  with no C toolchain, no Docker, no CI matrix gymnastics:
  ```bash
  CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o dist/camne.exe ./cmd/camne
  ```
- **Windows works.** The prior art has taken real bugs on Windows
  (`os.fchmod` missing before Python 3.13, `os.open` flag differences). Go's
  `os`/`filepath` packages make most of that class disappear.

Rejected alternatives:

| option | why not |
|---|---|
| cgo bindings (`go-skynet/go-llama.cpp`) | needs a C++ toolchain per target; destroys cross-compilation, which is the main reason to pick Go |
| purego bindings (`dianlight/gollama.cpp`) | CGO-free but still ships `libllama.{so,dylib,dll}` per platform, plus dlopen ABI drift on every llama.cpp release. Same file-shipping problem, harder failure mode to debug |
| pure-Rust inference (`candle`, `llama-gguf`) | months of quantization-kernel work to end up slower than llama.cpp. Correct only if the goal were learning inference internals. It is not |
| embedding the GGUF in the binary | a ~1 GB executable |

**Dependencies: none.** `net/http`, `os/exec`, `archive/zip`, `archive/tar`,
`encoding/json`, `crypto/sha256`, `flag`, `embed`. If you reach for a module,
justify it in the PR or do without.

### 4.2 Inference: drive `llama-server` over a local socket

llama.cpp does the inference. We do not bind to it, we talk to it.

- First query starts `llama-server` and leaves it resident. Cold start is
  dominated by reading a ~1 GB model off disk; paying it once instead of per
  query is the difference between a tool that feels instant and one slower than
  typing the command yourself. The prior art measured 5.5 s one-shot vs ~1.2 s
  of actual generation.
- **Use a UNIX domain socket in a `0700` directory, not a TCP port**, on
  platforms that have one. Loopback is shared across UIDs on a multi-user box,
  so a TCP `llama-server` is reachable by any co-tenant, and the bind-0-then-
  reopen dance leaves a window where another local process can squat the port
  and answer in our place with an arbitrary "generated command". Windows falls
  back to a loopback port; document the difference.
- **Constrain output with a GBNF grammar** to a single command line. This
  removes the entire class of markdown-fence-stripping and
  "Sure, here's the command:" post-processing. Free correctness, and one less
  parser to maintain.
- Greedy decoding, `temperature: 0`. Same question, same command, every time. A
  beginner tool must be predictable.
- `camne stop` shuts the resident server down. Idle timeout so it does not
  linger forever.

### 4.3 Zero-setup provisioning

This is the feature. Treat it as a first-class subsystem, not a script.

On first run, **announced, not asked** — camne states the total download size
in MB before it starts and ticks the MB as they land, but it does not stop for
a yes. Nothing works without these files, so a prompt would only offer a choice
between camne working and camne doing nothing:

1. Detect `runtime.GOOS`/`GOARCH`, and on Linux detect glibc version — builds
   from llama.cpp releases require glibc ≥ 2.34 and simply will not start on
   older distros. Fall back to a compatibility build.
2. Fetch the matching llama.cpp release asset from the GitHub releases API,
   pinned to a known-good build tag. Verify against the `sha256:` digests the
   release API exposes.
3. Fetch the GGUF from Hugging Face (`/resolve/main/`), verifying the
   `x-linked-etag` sha256 and `x-linked-size`.
4. Verify **before** unpacking or executing, never after.
5. Everything lands under `os.UserCacheDir()` — `%LOCALAPPDATA%`,
   `~/Library/Caches`, `~/.cache` handled for free.
6. Resume interrupted downloads. On a student's connection a 1 GB download
   *will* be interrupted.

`camne doctor` reports which piece is missing and how to fix it. That is a
diagnostic, not a required step.

Failure messages must be readable by someone who has never used a terminal
before. "Muat turun gagal, cuba lagi" beats a Go stack trace.

### 4.4 Safety checker

**Read [`whatisit_pkg/whatisit/safety.py`](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/master/whatisit_pkg/whatisit/safety.py)
and its module docstring before writing a line of this.** It documents a
checker that was rewritten after an adversarial audit found it was
simultaneously evadable and noisy. Do not re-derive those bugs.

The design that survived, and which we port:

1. Strip terminal control bytes — model output is untrusted and lands in a
   terminal where escape sequences can repaint what the user is about to
   approve.
2. Tokenize properly (Go: `mvdan.cc/sh/syntax` is the correct parser, but it is
   a dependency — start with a `shlex`-equivalent in-tree). Quoting must not be
   a variable: `rm -rf '/'` and `rm -rf /` are the same command.
3. Normalize long options to short: `rm --recursive --force` is `rm -rf`.
4. Extract the actual **target arguments** of destructive verbs.
5. Ask whether a target **is** a critical path, never whether one **appears
   in** it. `/home` is critical; `/home/ariff/project/build` is not. Prefix
   matching here was a real false-positive bug, and a checker that cries wolf
   trains users to ignore it.
6. Unresolvable targets (`$VAR`, command substitution) are dangerous by
   default. `rm -rf $EMPTY/` is the canonical way people destroy machines.

This is a denylist over a Turing-complete language. It is a seatbelt, not a
sandbox. **The real protection is that the default path never executes
anything.** Keep it that way.

Warnings render in Malay. Port the test suite from
`whatisit_pkg/tests/test_safety.py` first — those tests encode the audit.

## 5. The model

### 5.1 Bake-off: run both, publish both

Which base wins is an open question and the answer is worth two LoRA runs
(~2 h on one A100, same dataset for both). **Do not pick on vibes. Measure.**

| base | the bet | approx Q4_K_M size |
|---|---|---|
| [Gemma-SEA-LION-v4.5-E2B-IT](https://huggingface.co/aisingapore/Gemma-SEA-LION-v4.5-E2B-IT-GGUF) | Bahasa Melayu is a first-class target language; Gemma pretraining carries some shell knowledge | ~1.8 GB |
| [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct) | the model does not need to *understand* Malay, only to map Malay phrasing onto commands — a narrow task a code model may learn from 125k pairs | 941 MB |
| [mesolitica/mallam-1.1b](https://huggingface.co/mesolitica/mallam-1.1b-20k-instructions) | Malay-native including slang and regional variants; shell knowledge likely thin. Third seat, run if the first two disappoint | ~700 MB |

The Qwen bet is the one to root for: it keeps 941 MB and ~40 tok/s on 4 cores.
If it holds up, the tool is half the size and twice the speed on the target
machine. If it does not, SEA-LION is the honest answer and we pay the latency.

### 5.2 Training setup

Start from the recipe the prior art already validated — it reached 0.620 on
InterCode-ALFA from a 0.540 base, +0.080 paired, p = 0.004 on exact McNemar.
Do not go inventing hyperparameters before there is a baseline.

| | |
|---|---|
| method | LoRA, merged into base in bf16, → f16 GGUF, → Q4_K_M |
| rank / alpha / dropout | 32 / 64 / 0.05 |
| target modules | all linear (`q,k,v,o,gate,up,down`) |
| LR / schedule | 2e-4, cosine, 3% warmup |
| epochs | 2, packing off |
| batch | 16 × 2 grad accum, seq len 512 |
| precision | bf16, seed 42 |
| hardware | one A100 80GB, ~1 h |

Change one thing at a time and record what it bought. Seed 42 everywhere so
runs are comparable.

## 6. The dataset is the actual project

The CLI is a couple of weekends. The data is the risk. Budget accordingly.

Base pool: [NL2SH-ALFA](https://huggingface.co/datasets/westenfelder/NL2SH-ALFA)
plus the pool the prior art assembled (Fig specs, tldr-pages, cli-commands-
explained, command-generation, git-instruction — 125,770 rows, licences listed
in that repo's `NOTICE`).

Translating the English prompts is maybe 10% of the work. The other 90%:

### 6.1 Register — the thing that decides whether this works

Machine translation produces `Bagaimanakah cara untuk mencari fail...`. Nobody
types that. Users type `camne nak cari file`. A model trained only on formal
Malay will score well on a formal eval and fail every real user.

Generate **four registers per pair**, keeping the command byte-identical:

| register | example for "find files over 100MB" |
|---|---|
| formal BM | `Bagaimanakah cara mencari fail melebihi 100MB` |
| colloquial | `camne nak cari file lagi besar dari 100MB` |
| rojak | `macam mana nak list files yang size besar dari 100MB` |
| English | `find files bigger than 100MB` |

Colloquial markers to cover deliberately: `camne`, `macam mana`, `macam mana
nak`, `nak`, `kat`, `ni`, `tu`, `je`, `dah`, `boleh tak`, `tolong`, `tunjuk`,
`buat`, `letak`, `buang`. Include the shortenings people actually type — `mcm
mana`, `cmne`, `tlg`.

### 6.2 Technical nouns stay English

Malaysians say *file*, *folder*, *delete*, *download*, *compress*, *server* —
not *fail*, *folder*, *padam*, *muat turun*, *mampat*, *pelayan*. A translation
API will "correct" every one of these and poison the entire set.

Post-process with a stoplist that forces technical vocabulary back to English.
Then **read 200 rows by hand** before training on 125k. If the samples read
like a government circular, the pipeline is broken and no amount of training
will fix it.

### 6.3 Commands are never translated

The NL side is translated. The command side is byte-identical to the source.
This is what makes the whole approach cheap, and it is also what lets the
existing benchmark scorer work unmodified.

## 7. Benchmarking — required, not optional

**Every model change ships with numbers.** No merging a model on the strength of
a few nice-looking examples.

### 7.1 Accuracy

Use [InterCode-ALFA](https://github.com/westenfelder/InterCode-ALFA), the
scorer from the NAACL 2025 NL2SH paper. It runs each generated command in a
container and diffs the resulting filesystem and stdout against a reference.
300 tasks, pass/fail each.

- Translate the 300 task prompts into **colloquial** Malay, not formal. A
  formal-register eval reports a score your users will never experience.
- Commands are language-neutral, so the **scorer runs unmodified**. Do not
  patch it — a modified scorer produces numbers nobody can compare against.
- Keep the English 300 as a control. Regression there means the tune damaged
  general ability.
- Fixed settings, stated with every number: temperature 0, `max_tokens=64`,
  embedding heuristic threshold 0.75.
- Report significance: paired **exact McNemar** against the untuned base, with
  a 95% CI. 300 tasks cannot resolve small differences, and saying so is part
  of the result. "Roughly matches a 7B" is an honest claim; "beats a 7B" from a
  0.007 gap is not.

This BM-register eval set does not exist yet. Building it is a real
contribution — publish it.

### 7.2 Performance, on the target machine

Every candidate model, same box, same thread count, stated:

| metric | how |
|---|---|
| generation | tok/s, median of ≥ 12 queries |
| warm answer latency | wall clock, server already resident, median |
| cold start | first query including model load |
| resident RSS | after warm-up |
| size on disk | GGUF bytes |
| install wall time | download + verify + unpack, on a normal connection |

Sweep thread count (2, 4, 6, 8) — on a 4-core box more threads is not more
speed, and the default must be right out of the box.

### 7.3 The table that goes in the README

Publish it in the shape the prior art used, so the two are comparable:

| model | size on disk | BM pass rate | EN pass rate | tok/s @4t | RSS |
|---|---|---|---|---|---|

Include the untuned bases as rows. A tune that does not beat its own base is
not a result.

## 8. Milestones

1. **Skeleton** — `camne <words>` → hardcoded command. Cross-compile script
   produces all six binaries. Proves the distribution story.
2. **Provisioning** — download, verify, unpack, resume, `doctor`. Test on a
   fresh VM per platform with nothing installed. This is the differentiator;
   get it right before the model is good.
3. **Engine** — resident `llama-server`, socket transport, GBNF grammar, using
   the *existing English* whatisit model. End-to-end working tool, wrong
   language.
4. **Safety** — port the checker and its full test suite, Malay strings.
5. **Data** — build the pipeline, hand-review samples, publish the dataset.
6. **Bake-off** — tune both bases, run both evals, publish the table, pick.
7. **Release** — GitHub Releases, Homebrew tap, Scoop manifest, `go install`.
   None of these require a runtime on the user's machine.

Milestone 3 uses the English model deliberately: it decouples "does the tool
work" from "does the model speak Malay", so the two never fail at the same time.

## 9. References

**Prior art, directly reused**
- [ThorOdinson246/whatisit-nl2sh](https://github.com/ThorOdinson246/whatisit-nl2sh) — architecture, safety checker, training recipe, benchmark methodology. Apache-2.0.
- [`safety.py`](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/master/whatisit_pkg/whatisit/safety.py) — read the docstring before touching safety.
- [`engine.py`](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/master/whatisit_pkg/whatisit/engine.py) — resident-server and socket rationale.
- [`fetch.py`](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/master/whatisit_pkg/whatisit/fetch.py) — download/verify/glibc-fallback logic.

**Research and benchmark**
- [westenfelder/NL2SH](https://github.com/westenfelder/NL2SH) — NAACL 2025, LLM-Supported Natural Language to Bash Translation.
- [westenfelder/InterCode-ALFA](https://github.com/westenfelder/InterCode-ALFA) — the scorer.
- [NL2SH-ALFA dataset](https://huggingface.co/datasets/westenfelder/NL2SH-ALFA)
- [Local LLMs for NL2Bash, NDSS 2026](https://www.ndss-symposium.org/wp-content/uploads/lastx2026-49.pdf)

**Models**
- [Gemma-SEA-LION-v4.5-E2B-IT-GGUF](https://huggingface.co/aisingapore/Gemma-SEA-LION-v4.5-E2B-IT-GGUF) · [sea-lion.ai](https://sea-lion.ai/)
- [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct)
- [mesolitica/mallam-1.1b](https://huggingface.co/mesolitica/mallam-1.1b-20k-instructions) · [MaLLaM paper](https://arxiv.org/pdf/2401.14680)
- [ThorOdinson246/nl2sh-1.5b-Q4_K_M](https://huggingface.co/ThorOdinson246/nl2sh-1.5b-Q4_K_M) — the English model, for milestone 3.

**Runtime**
- [llama.cpp](https://github.com/ggml-org/llama.cpp) · [releases](https://github.com/ggml-org/llama.cpp/releases) · [GBNF grammars](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)

**Comparable tools, for positioning**
- [djcopley/ShellOracle](https://github.com/djcopley/ShellOracle) · [sigoden/aichat](https://github.com/sigoden/aichat) · [TheR1D/shell_gpt](https://github.com/TheR1D/shell_gpt) · [BuilderIO/ai-shell](https://github.com/BuilderIO/ai-shell)

## 10. Licensing

Settle this before publishing weights, not after.

- Apache-2.0 for this repo, matching the prior art.
- A `NOTICE` file listing every training-data source with its licence and share
  of the pool. Copy the prior art's format; it is exemplary. tldr-pages is
  CC-BY-4.0 and **requires** attribution.
- **Base model licences differ and this affects the bake-off**: Qwen2.5-Coder
  is Apache-2.0; SEA-LION inherits Gemma terms, which are not Apache-2.0 and
  carry use restrictions. If SEA-LION wins on accuracy, the licence cost is a
  real part of the decision — record it in the bake-off table, not in a
  footnote discovered at release time.
- Translated data inherits the source licence. Note which translation service
  produced it and check its terms on derived datasets.

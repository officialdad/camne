<p align="center">
  <img src="camne-hero-640x640.png" alt="camne logo" width="160">
</p>

# camne

[![CI](https://github.com/officialdad/camne/actions/workflows/ci.yml/badge.svg)](https://github.com/officialdad/camne/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/officialdad/camne)](https://github.com/officialdad/camne/releases/latest)
[![Go](https://img.shields.io/github/go-mod/go-version/officialdad/camne)](go.mod)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Ask a terminal question in Malay, get the command back.

*camne* is how people say *macam mana* / *bagaimana*: "how". Type it the way
you would ask a friend.

```console
$ camne nak exit vim
<Esc>:q<Enter>

$ camne nak tengok fail hidden
ls -a

$ camne nak pasang zsh
  camne warning: runs as root
sudo apt install zsh

$ camne nak list port bukak
lsof -i
```

![camne demo: five beginner questions typed in colloquial Malay, each answered with one English shell command; the one that needs root gets a magenta camne warning line above it](demo/demo.gif)

camne only prints the command. It never runs it. You read it, then you decide
whether to type it.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh
```

Then ask something:

```sh
camne nak reset password
```

The first time, camne downloads what it needs (about 1 GB, once) and shows the
progress. After that it works offline. Your questions never leave your
computer.

On Windows, download `camne_windows_amd64.exe` (or `camne_windows_arm64.exe`)
from [Releases](https://github.com/officialdad/camne/releases).

Already installed? `camne update` gets the newest version.

## How to ask

Colloquial Malay, rojak, or English all work. camne answers in English either
way, because commands are English.

```console
$ camne nak cari file besar dari 100MB dalam home
find ~ -size +100M

$ camne nak kira berapa banyak file dalam folder ni
find . -type f | wc -l

$ camne how do I see disk space
df -h
```

Questions about the terminal itself count too: which flag does what, which
tool to reach for, how to get out of an editor.

**Spelling changes the answer.** Bahasa pasar spelling is fine (`bukak`,
`tgk`, `mcm mana`), but the same question spelled two ways can come back with
two different commands. `nak list port bukak` gives `lsof -i`; `nak list port
buka` gives `netstat -an | grep -i listen`. Both list open ports. If an answer
looks off, ask again in different words. This is a beta model trained mostly
on standard spelling; the pasar forms are still being added.

## Warnings

Some commands deserve a second look before you run them: anything that
deletes, anything that needs root, anything that touches a system folder.
camne prints a magenta `camne warning:` line above those, one line per reason.

```console
$ camne nak delete semua file dalam /etc
  camne warning: find + delete: target is the critical path /etc
find /etc -type f -exec rm {} \;
```

The command still prints. camne runs nothing, warned or not.

## Other commands

| command | what it does |
|---|---|
| `camne doctor` | checks the install and says what is missing, without downloading anything |
| `camne update` | installs the newest release in place |
| `camne stop` | shuts down the model camne keeps in memory between questions |

Once a day, after it has answered, camne asks GitHub whether a newer release
exists and offers to install it. Nothing downloads until you say yes, and the
check is skipped when camne's output is piped somewhere.

## For the curious

The rest of this file is about how camne works and how well it works. You do
not need any of it to use camne.

### What runs on your machine

camne is one Go binary. On first run it fetches
[llama-server](https://github.com/ggml-org/llama.cpp) and the
[camne-1.5b](https://huggingface.co/opariffazman/camne-1.5b-Q4_K_M) model into
`~/.cache/camne`. Both stay local. There is no account, no telemetry, and no
network call except the download and the once-a-day release check.

It runs on 4 cores and 8 GB of RAM with no GPU. Warm answers take under a
second; a cold start is under two.

The command is syntax-highlighted and the warnings are coloured only when the
output is a terminal. Pipe it anywhere (`camne ... | sh`, `$(camne ...)`) and
you get plain bytes. `NO_COLOR` or `TERM=dumb` turns colour off everywhere.

### The model

camne-1.5b is Qwen2.5-Coder-1.5B tuned on 76k command pairs in four
registers (formal Malay, colloquial, rojak, English) plus 330 hand-written
beginner tasks. Status: beta.

Malay and rojak questions answer well, and the first fifty things a beginner
asks (create, list, delete, copy, find, disk, permissions, "how do I quit
vim") pass 90% of unseen phrasings on the repo's probe. On advanced English
one-liners it is worse than the English-only model it replaces (-0.06,
p = 0.036). If you only ever type English, use
[whatisit](https://github.com/ThorOdinson246/whatisit-nl2sh).

Scores below are [InterCode-ALFA](https://github.com/westenfelder/InterCode-ALFA),
unmodified scorer, 300 tasks per register. Rojak, Malay grammar around
English technical nouns, is what people type most, so it is the column that
matters.

| model | BM | rojak | EN | beginner tasks* | size | tok/s @4t | RSS |
|---|---|---|---|---|---|---|---|
| nl2sh-1.5b (the English model camne used to ship) | 0.310 | 0.447 | **0.603** | — | 986 MB | 40 | 1.6 GB |
| camne-1.5b, previous revision | 0.437 | 0.490 | 0.553 | 0.79 | 986 MB | 40 | 1.6 GB |
| **camne-1.5b, this revision** | **0.487** | 0.490 | 0.543 | **0.90** | 986 MB | 37 | 1.6 GB |

\* `training/probe.py`: 35 beginner tasks asked in 177 phrasings the training
data does not contain, scored on whether the right tool comes back.

Against the English model: Malay +0.177 (p = 3e-08), rojak +0.043 (p = 0.13,
unresolved at 300 tasks), English -0.060 (p = 0.036). Against the previous
revision the benchmark cannot tell them apart; the beginner probe can (+0.11,
p = 0.002). Speed and memory are unchanged: same base, same quantisation,
same file size.

Full method, the runs that failed, and why, in [RESULTS.md](RESULTS.md).

### Build from source

```sh
go build ./cmd/camne        # local binary
scripts/build.sh v0.1.0     # all six targets into dist/ + checksums.txt
vhs demo/demo.tape          # re-record demo.gif
```

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). The repo ships a checked-in
`.claude/` config, described in [`.claude/README.md`](.claude/README.md).

## License

Apache-2.0

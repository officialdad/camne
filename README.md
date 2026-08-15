<p align="center">
  <img src="camne-hero-640x640.png" alt="camne logo" width="160">
</p>

# camne

[![CI](https://github.com/officialdad/camne/actions/workflows/ci.yml/badge.svg)](https://github.com/officialdad/camne/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/officialdad/camne)](https://github.com/officialdad/camne/releases/latest)
[![Go](https://img.shields.io/github/go-mod/go-version/officialdad/camne)](go.mod)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

> **Status: the Malay model has landed.** camne now runs
> [camne-1.5b](https://huggingface.co/opariffazman/camne-1.5b-Q4_K_M), tuned on
> 307k four-register rows. Malay and rojak questions answer well; English is
> roughly level with the model it replaces. Numbers in [RESULTS.md](RESULTS.md).

*camne* is how people say *macam mana* / *bagaimana*: "how".

Ask a terminal question in Malay, get the command back. Everything runs on your
machine and there is nothing to set up.

![camne demo: a colloquial Malay question and the syntax-highlighted English command it prints, a magenta `camne warning:` line above a command that touches /etc, and `camne doctor` on a fresh machine](demo/demo.gif)

```console
$ camne nak cari file besar dari 100MB dalam home
find ~ -type f -size +100M
```

It is not only for "do this task for me". Questions about the CLI itself count
too: which flag does what, which tool to reach for, how a shell shortcut works.
The answer comes back as one command line, and camne only prints it. Nothing
runs.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh
```

The installer puts the binary in `/usr/local/bin` if that directory is
writable, otherwise `~/.local/bin`. It tells you when that directory is not on
your `PATH` yet.

Already installed? Run `camne update` — it replaces the binary in place, so the
installer is a first-time-only step.

Windows: download `camne_windows_amd64.exe` (or `camne_windows_arm64.exe`) from
[Releases](https://github.com/officialdad/camne/releases).

## Usage

On first run camne downloads llama-server and the model (about 1 GB, once),
printing the size before it starts and the progress while it runs. After that
it works offline, so your questions never leave the machine. To see what is
missing without downloading anything, run `camne doctor`.

```console
$ camne cari file lagi besar dari 100MB
find / -size +100M

$ camne nak delete semua file dalam /etc
  camne warning: find + delete: target is the critical path /etc
find /etc -type f -exec rm {} \;
```

Anything the safety checker flags gets one bright-magenta `camne warning:` line
per reason, on stderr, above the command. Dangerous and merely-worth-a-second-
look commands share that one shape — the reason is what tells them apart. camne
prints either way and executes neither.

The command is syntax-highlighted and the warnings are coloured only when the
output is a terminal. Pipe it anywhere (`camne ... | sh`, `$(camne ...)`) and
you get plain bytes, which is what any program reading camne's output would
see. `NO_COLOR` or `TERM=dumb` turns colour off everywhere.

You type Malay; camne answers in English. The question can be colloquial
(`camne nak buat file baru`), rojak, or plain English — the command and every
line camne prints come back in English.

Three other commands: `camne doctor` checks the install, `camne stop` shuts down
the model held in memory, and `camne update` installs the newest release.

Once a day, after it has printed an answer, camne asks GitHub whether a newer
release exists and offers to install it — nothing is downloaded or replaced
until you answer the prompt. The check sends nothing but that question, never
runs before the answer, and is skipped entirely when camne's output is piped
somewhere.

## The model

[InterCode-ALFA](https://github.com/westenfelder/InterCode-ALFA), unmodified
scorer, 300 tasks per register. Rojak — Malay grammar around English technical
nouns — is what people actually type, so it is the column that matters.

| model | BM | rojak | EN | size | tok/s @4t | RSS |
|---|---|---|---|---|---|---|
| nl2sh-1.5b (the English model camne used to ship) | 0.297 | 0.430 | **0.593** | 986 MB | 40 | 1.6 GB |
| **camne-1.5b** | **0.417** | **0.490** | 0.533 | 986 MB | 40 | 1.6 GB |

Malay +0.120 (p=0.0002) and rojak +0.060 (p=0.044) against the model it
replaces. English is −0.060 at p=0.050, which 300 tasks cannot resolve — so
the honest claim is "cannot distinguish", not "as good as". Speed and memory
are unchanged: same base, same quantisation, same file size.

Full method, the runs that failed, and why, in [RESULTS.md](RESULTS.md).

## Build from source

```sh
go build ./cmd/camne        # local binary
scripts/build.sh v0.1.0     # all six targets into dist/ + checksums.txt
vhs demo/demo.tape          # re-record demo.gif
```

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). The repo ships a checked-in
`.claude/` config, described in [`.claude/README.md`](.claude/README.md).

## License

Apache-2.0

<p align="center">
  <img src="camne-hero-640x640.png" alt="camne logo" width="160">
</p>

# camne

[![CI](https://github.com/officialdad/camne/actions/workflows/ci.yml/badge.svg)](https://github.com/officialdad/camne/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/officialdad/camne)](https://github.com/officialdad/camne/releases/latest)
[![Go](https://img.shields.io/github/go-mod/go-version/officialdad/camne)](go.mod)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

> **Status: work in progress.** The engine works today, but it runs an English
> model (nl2sh-1.5b). The Malay model is still training, so colloquial and
> rojak questions will not answer well yet.

*camne* is how people say *macam mana* / *bagaimana*: "how".

Ask a terminal question in Malay, get the command back. Everything runs on your
machine and there is nothing to set up.

![camne demo: a colloquial Malay question, the syntax-highlighted command it prints, a red BAHAYA line, the same query piped into `cat` to show plain output, and `camne doctor` on a fresh machine](demo/demo.gif)

```console
$ camne nak buat file baru
touch file.txt
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

Windows: download `camne_windows_amd64.exe` (or `camne_windows_arm64.exe`) from
[Releases](https://github.com/officialdad/camne/releases).

## Usage

On first run camne downloads llama-server and the model (about 1 GB, once),
printing the size before it starts and the progress while it runs. After that
it works offline, so your questions never leave the machine. To see what is
missing without downloading anything, run `camne doctor`.

```console
$ camne cari file lagi besar dari 100MB
find / -size +100M -type f -exec ls -lh {} \; | sort -n -k5

$ camne nak delete semua file dalam /etc
!! BAHAYA
find /etc -type f -exec rm {} \;
```

Dangerous commands get a red `!! BAHAYA` line; anything merely worth a second
look gets a yellow `!  Awas` line. camne prints either way and executes
neither.

The command is syntax-highlighted and the warnings are coloured only when the
output is a terminal. Pipe it anywhere (`camne ... | sh`, `$(camne ...)`) and
you get plain bytes. That is the third scene in the demo above: the same query
sent through `cat` comes back with no colour, which is what any program reading
camne's output would see. `NO_COLOR` or `TERM=dumb` turns colour off
everywhere.

Three other commands: `camne doctor` checks the install, `camne stop` shuts down
the model held in memory, and `camne update` installs the newest release.

Once a day, after it has printed an answer, camne asks GitHub whether a newer
release exists and offers to install it — nothing is downloaded or replaced
until you answer the prompt. The check sends nothing but that question, never
runs before the answer, and is skipped entirely when camne's output is piped
somewhere.

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

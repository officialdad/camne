<p align="center">
  <img src="camne-hero-640x640.png" alt="camne logo" width="160">
</p>

# camne

[![CI](https://github.com/officialdad/camne/actions/workflows/ci.yml/badge.svg)](https://github.com/officialdad/camne/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/officialdad/camne)](https://github.com/officialdad/camne/releases/latest)
[![Go](https://img.shields.io/github/go-mod/go-version/officialdad/camne)](go.mod)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Ask in Malay, get a shell command. Fully local, zero setup.

![camne demo: a colloquial Malay question, the syntax-highlighted command it prints, a red BAHAYA block, and `camne doctor` on a fresh machine](demo/demo.gif)

```console
$ camne nak buat file baru
touch file.txt
```

camne only prints the command. It never runs anything.

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
printing the size before it starts and the progress while it runs. Once
everything is in place it all runs offline, so your questions never leave the
machine. To see what is missing without downloading anything, run
`camne doctor`.

The interface is Malay, because that is the point. Colloquial and rojak both
work, and English still works too.

```console
$ camne cari file lagi besar dari 100MB
find / -size +100M -type f -exec ls -lh {} \; | sort -n -k5

$ camne nak delete semua file dalam /etc
!! BAHAYA !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   find + delete: target ialah laluan kritikal /etc — tukar
   target ke folder yang kau betul-betul nak
   camne cuma tunjuk command ni je — ia tak jalankan
   apa-apa, dan tak akan.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
find /etc -type f -exec rm {} \;
```

Dangerous commands get a red `!! BAHAYA` block that says what to do about
them; anything merely worth a second look gets a yellow `!  Awas:` line. camne
never executes anything regardless, it only prints.

The command itself is syntax-highlighted, and the warnings are coloured, only
when the stream is a terminal. Pipe it — `camne ... | sh`, `$(camne ...)` — and
you get exactly the plain bytes you always did. `NO_COLOR` or `TERM=dumb` turns
colour off everywhere.

Also: `camne doctor` (check the install), `camne stop` (shut down the model
held in memory).

## Status

The engine works with an English model (nl2sh-1.5b). The Malay model
(colloquial + rojak) is still in progress. [PROMPT.md](PROMPT.md) has the full
plan.

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

# camne

[![CI](https://github.com/officialdad/camne/actions/workflows/ci.yml/badge.svg)](https://github.com/officialdad/camne/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/officialdad/camne)](https://github.com/officialdad/camne/releases/latest)
[![Go](https://img.shields.io/github/go-mod/go-version/officialdad/camne)](go.mod)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Tanya dalam BM, dapat shell command. Fully local, zero setup.

![Demo camne: soalan BM colloquial, command keluar, banner BAHAYA, dan skrin kebenaran download kali pertama](demo/demo.gif)

```console
$ camne nak buat file baru
touch file.txt
```

`camne` hanya tunjuk command — ia tak jalankan apa-apa.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh
```

Installer letak binary dalam `/usr/local/bin` kalau folder tu boleh ditulis,
kalau tak dalam `~/.local/bin` — dan ia akan beritahu kalau folder tu belum ada
dalam `PATH` anda.

Windows: muat turun `camne_windows_amd64.exe` (atau `camne_windows_arm64.exe`)
dari [Releases](https://github.com/officialdad/camne/releases).

## Cara guna

Kali pertama, camne akan tanya kebenaran untuk download llama-server dan model
(lebih kurang 1 GB, sekali je). Jawab bukan `y` — takde apa yang di-download.
Lepas semua lengkap, semua jalan offline — soalan anda tak keluar dari mesin
langsung.

```console
$ camne cari file lagi besar dari 100MB
find / -size +100M -type f -exec ls -lh {} \; | sort -n -k5

$ camne nak delete semua file dalam /etc
  !! BAHAYA  find + delete: target ialah laluan kritikal /etc
find /etc -type f -exec rm {} \;
```

Command yang bahaya dapat banner `!! BAHAYA` — dan camne tak pernah jalankan
apa-apa, ia hanya tunjuk.

Lain: `camne doctor` (semak pemasangan), `camne stop` (hentikan model dalam
memory).

## Status

Engine siap dengan model English (nl2sh-1.5b). Model Malay (colloquial +
rojak) sedang dibangunkan — lihat [PROMPT.md](PROMPT.md) untuk pelan penuh.

## Build dari source

```sh
go build ./cmd/camne        # binary tempatan
scripts/build.sh v0.1.0     # semua 6 target ke dist/ + checksums.txt
vhs demo/demo.tape          # rakam semula demo.gif
```

## Lesen

Apache-2.0

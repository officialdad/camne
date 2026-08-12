# camne

Tanya dalam BM, dapat shell command. Fully local, zero setup.

```console
$ camne nak buat file baru
touch nama_fail.txt
```

`camne` hanya tunjuk command — ia tak jalankan apa-apa.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh
```

Windows: muat turun `camne_windows_amd64.exe` dari
[Releases](https://github.com/officialdad/camne/releases).

## Status

Milestone 1 (skeleton): jawapan datang dari keyword table sementara.
Model tempatan penuh (Malay in, command out, offline) menyusul — lihat
[PROMPT.md](PROMPT.md) untuk pelan penuh.

## Build dari source

```sh
go build ./cmd/camne        # binary tempatan
scripts/build.sh v0.1.0     # semua 6 target ke dist/
```

## Lesen

Apache-2.0

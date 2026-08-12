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

## Cara guna

Kali pertama, camne akan tanya kebenaran untuk download model (~1 GB, sekali
je). Lepas tu semua jalan offline — soalan anda tak keluar dari mesin langsung.

```console
$ camne cari file lagi besar dari 100MB
find / -size +100M -exec ls -lh {} \;

$ camne padam semua benda dalam root
  !! BAHAYA  find + delete: target ialah laluan kritikal /
find / -exec rm -rf {} \;
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
scripts/build.sh v0.1.0     # semua 6 target ke dist/
```

## Lesen

Apache-2.0

#!/bin/sh
# camne installer — muat turun binary dari GitHub Releases, sahkan checksum,
# letak dalam PATH. Guna: curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh
set -eu

REPO="officialdad/camne"
BASE="https://github.com/$REPO/releases/latest/download"

case "$(uname -s)" in
	Linux)  os=linux ;;
	Darwin) os=darwin ;;
	*) echo "Maaf, camne tak support OS ni: $(uname -s)." >&2
	   echo "Untuk Windows, muat turun camne.exe dari https://github.com/$REPO/releases" >&2
	   exit 1 ;;
esac

case "$(uname -m)" in
	x86_64|amd64)  arch=amd64 ;;
	arm64|aarch64) arch=arm64 ;;
	*) echo "Maaf, camne tak support CPU ni: $(uname -m)." >&2; exit 1 ;;
esac

BIN="camne_${os}_${arch}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "Muat turun camne ($os/$arch)..."
if ! curl -fsSL -o "$TMP/$BIN" "$BASE/$BIN" || ! curl -fsSL -o "$TMP/checksums.txt" "$BASE/checksums.txt"; then
	echo "Muat turun gagal. Semak internet anda dan cuba lagi." >&2
	exit 1
fi

# Verify BEFORE installing, never after.
if command -v sha256sum >/dev/null 2>&1; then
	SUM=$(sha256sum "$TMP/$BIN" | cut -d' ' -f1)
else
	SUM=$(shasum -a 256 "$TMP/$BIN" | cut -d' ' -f1)
fi
WANT=$(grep " $BIN\$" "$TMP/checksums.txt" | cut -d' ' -f1)
if [ -z "$WANT" ] || [ "$SUM" != "$WANT" ]; then
	echo "Checksum tak sepadan — fail mungkin rosak atau diubah. Tak install. Cuba lagi." >&2
	exit 1
fi

if [ -w /usr/local/bin ]; then
	DIR=/usr/local/bin
else
	DIR="$HOME/.local/bin"
	mkdir -p "$DIR"
fi

chmod +x "$TMP/$BIN"
mv "$TMP/$BIN" "$DIR/camne"

echo "Siap! camne dah dipasang di $DIR/camne"
case ":$PATH:" in
	*":$DIR:"*) ;;
	*) echo "Nota: tambah $DIR dalam PATH anda dulu, contoh:"
	   echo "  export PATH=\"\$PATH:$DIR\"" ;;
esac
echo "Cuba: camne nak buat file baru"

#!/bin/sh
# camne installer — muat turun binary dari GitHub Releases, sahkan checksum,
# letak dalam PATH. Guna: curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh
set -eu

REPO="officialdad/camne"

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

# Retry wrapper: flaky connections drop mid-transfer, and curl's --retry-all-errors
# needs 7.71+. fetch <output> <url>
fetch() {
	for _try in 1 2 3; do
		curl -fsSL -o "$1" "$2" && return 0
		sleep 2
	done
	return 1
}

# The /releases/latest/download alias is flaky on some networks; resolve the
# tag via the API and use the versioned URL instead.
fetch "$TMP/release.json" "https://api.github.com/repos/$REPO/releases/latest" || true
TAG=$(sed -n 's/^[[:space:]]*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' "$TMP/release.json" 2>/dev/null | head -1)
if [ -z "$TAG" ]; then
	echo "Tak jumpa release terbaru. Semak internet anda dan cuba lagi." >&2
	exit 1
fi
BASE="https://github.com/$REPO/releases/download/$TAG"

echo "Muat turun camne $TAG ($os/$arch)..."
if ! fetch "$TMP/$BIN" "$BASE/$BIN" || ! fetch "$TMP/checksums.txt" "$BASE/checksums.txt"; then
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

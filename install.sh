#!/bin/sh
# camne installer — downloads the binary from GitHub Releases, verifies its
# checksum, puts it in PATH. Use: curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh
set -eu

REPO="officialdad/camne"

case "$(uname -s)" in
	Linux)  os=linux ;;
	Darwin) os=darwin ;;
	*) echo "Sorry, camne does not support this OS: $(uname -s)." >&2
	   echo "On Windows, download camne.exe from https://github.com/$REPO/releases instead." >&2
	   exit 1 ;;
esac

case "$(uname -m)" in
	x86_64|amd64)  arch=amd64 ;;
	arm64|aarch64) arch=arm64 ;;
	*) echo "Sorry, camne does not support this CPU: $(uname -m)." >&2
	   echo "Ask for it at https://github.com/$REPO/issues" >&2; exit 1 ;;
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
	echo "Could not find the latest release. Check your internet connection and try again." >&2
	exit 1
fi
BASE="https://github.com/$REPO/releases/download/$TAG"

echo "Downloading camne $TAG ($os/$arch)..."
if ! fetch "$TMP/$BIN" "$BASE/$BIN" || ! fetch "$TMP/checksums.txt" "$BASE/checksums.txt"; then
	echo "Download failed. Check your internet connection and try again." >&2
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
	echo "Checksum does not match — the file may be damaged or tampered with." >&2
	echo "Nothing was installed. Try again." >&2
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

echo "Done! camne is installed at $DIR/camne"
case ":$PATH:" in
	*":$DIR:"*) ;;
	*) echo "Note: add $DIR to your PATH first, like this:"
	   echo "  export PATH=\"\$PATH:$DIR\"" ;;
esac
echo "Try it: camne nak buat file baru"

#!/bin/sh
# Cross-compile camne for all six targets into dist/, plus checksums.txt.
# Usage: scripts/build.sh [version]
set -eu
cd "$(dirname "$0")/.."
VERSION="${1:-dev}"

rm -rf dist
mkdir dist

for target in linux/amd64 linux/arm64 darwin/amd64 darwin/arm64 windows/amd64 windows/arm64; do
	goos=${target%/*}
	goarch=${target#*/}
	out="dist/camne_${goos}_${goarch}"
	[ "$goos" = windows ] && out="$out.exe"
	CGO_ENABLED=0 GOOS="$goos" GOARCH="$goarch" \
		go build -trimpath -ldflags "-s -w -X main.version=$VERSION" -o "$out" ./cmd/camne
	echo "built $out"
done

(cd dist && sha256sum camne_* > checksums.txt)
echo "wrote dist/checksums.txt"

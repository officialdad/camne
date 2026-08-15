#!/bin/sh
# Publish dist/ as a GitHub Release. Run scripts/build.sh <tag> first.
# Usage: scripts/release.sh v1.2.3
#
# Runnable outside GitHub Actions: point gh at a scratch repo with
# GH_REPO=you/camne-test and try the whole thing before a real tag exists.
set -eu
cd "$(dirname "$0")/.."

TAG="${1:?usage: scripts/release.sh vMAJOR.MINOR.PATCH}"

# Fail before publishing a release named after a typo. build.sh stamps this
# same string into `camne --version`.
case "$TAG" in
	v[0-9]*.[0-9]*.[0-9]*) ;;
	*) echo "release.sh: tag '$TAG' is not a vMAJOR.MINOR.PATCH release tag" >&2; exit 1 ;;
esac

# Smoke test: the binary must report the tag it was named after. A wrong
# -ldflags is silent everywhere else.
BIN="dist/camne_$(go env GOOS)_$(go env GOARCH)"
[ -x "$BIN" ] || { echo "release.sh: $BIN missing — run scripts/build.sh '$TAG' first" >&2; exit 1; }
GOT=$("$BIN" --version)
[ "$GOT" = "camne $TAG" ] || {
	echo "release.sh: $BIN reports '$GOT', expected 'camne $TAG'" >&2
	exit 1
}

# --generate-notes builds "What's Changed" from the PRs merged since the
# previous tag. --notes-file is PREPENDED above it as a fixed header carrying
# what a changelog cannot know: how to install, how to verify, and what
# happens on first run.
#
# Asset names must stay exactly as build.sh emits them — install.sh downloads
# camne_${os}_${arch} and greps checksums.txt for " $BIN$".
gh release create "$TAG" \
	--title "camne ${TAG#v}" \
	--verify-tag \
	--generate-notes \
	--notes-file .github/release-header.md \
	dist/camne_* dist/checksums.txt

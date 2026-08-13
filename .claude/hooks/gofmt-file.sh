#!/bin/sh
# PostToolUse(Edit|Write): gofmt the file that was just written. No-op for everything else.
#
# Reads the hook payload on stdin, pulls tool_input.file_path, and stops immediately
# unless it ends in .go. gofmt failing means Claude wrote Go that does not parse, so
# exit 2 hands the error back to Claude instead of swallowing it.
#
# ponytail: grep+cut instead of a JSON parser, to avoid making jq a contributor
# dependency in a repo whose whole point is zero setup. Ceiling: a file path
# containing a quote or a backslash (Windows) extracts wrong — then gofmt errors
# loudly rather than silently. Upgrade path: jq -r '.tool_input.file_path'.

f=$(grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | cut -d'"' -f4)

case "$f" in
	*.go) ;;
	*) exit 0 ;;
esac

[ -f "$f" ] || exit 0

if ! out=$(gofmt -w "$f" 2>&1); then
	echo "gofmt failed on $f:" >&2
	echo "$out" >&2
	exit 2
fi

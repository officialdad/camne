#!/bin/sh
# Stop: the repo gate. `go build ./... && go test ./...` must pass before a turn ends.
# Exit 2 blocks the stop and hands the failure back to Claude, so a red build cannot
# end a session quietly. Silent on success.

input=$(cat)

# Loop guard: harness versions that send stop_hook_active mark a stop that is already
# a retry of this hook. Bail out there so a genuinely unfixable failure cannot spin.
case "$input" in
	*'"stop_hook_active":true'*) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

if ! out=$(go build ./... 2>&1); then
	echo "BLOCKED: go build ./... failed" >&2
	echo "$out" >&2
	exit 2
fi

if ! out=$(go test ./... 2>&1); then
	echo "BLOCKED: go test ./... failed" >&2
	echo "$out" >&2
	exit 2
fi

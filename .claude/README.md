# .claude/

Checked-in Claude Code config for this repo. Any Claude session started here picks
it up automatically. It enforces the rules in [`CLAUDE.md`](../CLAUDE.md)
mechanically — it does not replace them.

## Hooks

| When | Runs | On failure |
|------|------|------------|
| After every `Edit`/`Write` | [`hooks/gofmt-file.sh`](hooks/gofmt-file.sh) — `gofmt -w` on the touched file, `*.go` only | exit 2, gofmt's parse error goes back to Claude |
| When Claude tries to end the turn | [`hooks/verify.sh`](hooks/verify.sh) — `go build ./... && go test ./...` | exit 2, blocks the stop and hands back the failing output |

Both are plain `/bin/sh`, no `jq`, no dependency beyond the Go toolchain. Measured
on a 4-core box: gofmt hook ~3 ms for a non-Go file, `verify.sh` 0.4 s warm and
1.2 s cold. Run them by hand the same way the harness does:

```sh
echo '{"tool_name":"Edit","tool_input":{"file_path":"/abs/path/to/file.go"}}' \
  | .claude/hooks/gofmt-file.sh
echo '{"hook_event_name":"Stop"}' | CLAUDE_PROJECT_DIR=$PWD .claude/hooks/verify.sh
```

## Permissions

`permissions.allow` covers the commands used constantly here — `go build/test/vet/fmt`,
`gofmt`, `python3` on `dataset/` and `training/` scripts, `git status/diff/log`,
`gh issue|pr view/list`. All read-only or repo-standard.

Deliberately **not** allowlisted, so they still prompt:

- Anything that fetches over the network (`curl`, `wget`, `go mod download`).
  Constraint 4 says nothing leaves the machine; an allowlisted fetch is where that
  starts to leak.
- Starting `llama-server`. It binds a port and loads a multi-GB model — that is a
  decision a human makes, not a silent one.
- `python3 -c` and `python3` outside `dataset/` and `training/`. `-c` is arbitrary
  code execution wearing a familiar name.
- Anything destructive: `rm`, `git push`, `git reset --hard`.

Cross-compile lines from `CLAUDE.md` (`CGO_ENABLED=0 GOOS=… go build …`) still
prompt: a leading env assignment defeats prefix matching. That is fine, they are rare.

## Personal settings

`.claude/settings.local.json` is gitignored. Put your own permissions, model
choice, and env there — never in `settings.json`, which is shared.

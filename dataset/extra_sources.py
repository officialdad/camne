#!/usr/bin/env python3
"""Extract (nl, command) pairs from the two remaining public sources whatisit
used, into the same CSV shape the rest of the pipeline consumes. Stdlib only
apart from the parquet read, which uses the training venv.

  python3 extra_sources.py        # -> raw/extra.csv

  commandlinefu via b-mc2/cli-commands-explained   CC0-1.0    ~15k pairs
  0xrushi/git-instruction-dataset                  MIT        ~1.6k pairs

Both are filtered to single-line commands: camne's grammar emits one line, so
a multi-command answer cannot be produced or scored. git-instruction loses
most of its rows to that filter (1,636 of 9,008) — its answers are mostly
3-command workflows.

commandlinefu is user-submitted golf, which is where the crusty idiom comes
from. Rows whose command is pure shell trickery with no named tool are
dropped; the rest are kept and left to tldr's canonical examples to balance.
"""
import csv
import json
import os
import re
import subprocess
import sys

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")

# A command with no alphabetic tool name is a shell trick (`^foo^bar`, `!!`),
# not something to teach as an answer to a natural-language request.
HAS_TOOL = re.compile(r"^[\s(]*[a-zA-Z_][\w.+-]*\b")


def clean_cmd(cmd):
    cmd = cmd.strip()
    if len(cmd.splitlines()) != 1 or not (1 < len(cmd) < 200):
        return ""
    return cmd if HAS_TOOL.match(cmd) else ""


def commandlinefu():
    path = os.path.join(RAW, "cli_explained.json")
    if not os.path.exists(path):
        print("skip commandlinefu: raw/cli_explained.json missing", file=sys.stderr)
        return []
    out = []
    for r in json.load(open(path, encoding="utf-8")):
        cmd, title = clean_cmd(r.get("code") or ""), (r.get("title") or "").strip()
        if cmd and title:
            out.append((title, cmd))
    return out


def git_instruction():
    path = os.path.join(RAW, "git_instruction.parquet")
    if not os.path.exists(path):
        print("skip git-instruction: raw/git_instruction.parquet missing", file=sys.stderr)
        return []
    # parquet needs pyarrow, which lives in the training venv, not here.
    code = (
        "import pyarrow.parquet as pq, json;"
        f"print(json.dumps(pq.read_table({path!r}).to_pylist()))"
    )
    rows = json.loads(subprocess.run(
        ["uv", "run", "--project", os.path.join(RAW, "..", "..", "training"),
         "python", "-c", code],
        capture_output=True, text=True, check=True).stdout)
    out = []
    for r in rows:
        cmd, nl = clean_cmd(r.get("output") or ""), (r.get("instruction") or "").strip()
        if cmd and nl:
            out.append((nl, cmd))
    return out


def main():
    rows = commandlinefu() + git_instruction()
    seen, deduped = set(), []
    for nl, cmd in rows:
        if (nl.lower(), cmd) in seen:
            continue
        seen.add((nl.lower(), cmd))
        deduped.append((nl, cmd))
    out = os.path.join(RAW, "extra.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nl", "bash"])
        w.writerows(deduped)
    print(f"{len(deduped)} pairs -> {out}")


if __name__ == "__main__":
    main()

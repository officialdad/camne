#!/usr/bin/env python3
"""Drop rows whose command carries tldr's list/name placeholder idiom.

    python3 lists.py out/pool_v8.jsonl out/pool_v9.jsonl

`file1 file2 ...`, `argument1 argument2 ...`, `filename`, `file_name`,
`file_or_directory`, `directory_name`, `folder_name`: prior.py's rule caught
`path/to` and `<name>`, not these. Their NL is generic ("erase specific
files") and their command is not runnable, so together they teach the exact
wrong thing (issue #62: `git obliterate file_1 file_2 ...` answered
`nak delete file ni je`). Whole pairs go: every row sharing the id stem.
"""
import json, re, sys

LIST = re.compile(
    r"\b(\w+?)_?1 \1_?2\b|\s\.\.\.(?=\s|$)|\b(?:file_?name|file_or_directory|directory_name|folder_name)\b"
)


def stem(rid: str) -> str:
    return re.split(r"[+~]", rid, maxsplit=1)[0]


def main(src: str, dst: str) -> None:
    rows = [json.loads(l) for l in open(src) if l.strip()]
    bad = {stem(r["id"]) for r in rows if LIST.search(r["cmd"])}
    keep = [r for r in rows if stem(r["id"]) not in bad]
    with open(dst, "w") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{src}: {len(rows)} rows -> {dst}: {len(keep)} rows, dropped {len(rows)-len(keep)} ({len(bad)} pairs)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

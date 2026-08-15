#!/usr/bin/env python3
"""Hand-written beginner tasks -> training rows. Stdlib only.

  python3 basics.py            # basics.txt -> out/basics.jsonl

The 76k-pair pool is advanced one-liners; nobody wrote down the first fifty
things a beginner does, so `create a new file` had zero coverage in every
pool version (RESULTS.md, run 6). basics.txt is that list, written by hand:
real filenames, several phrasings per task on the axes probe.py measures,
four registers, commands byte-identical across every row of a block.

Block format (blank line between blocks, `#` lines ignored):

  cmd: touch notes.txt
  F: formal BM | another formal phrasing
  C: colloquial | ...
  R: rojak | ...
  E: english | ...
"""
import json
import os
import sys

REG = {"F": "formal", "C": "colloquial", "R": "rojak", "E": "english"}
HERE = os.path.dirname(os.path.abspath(__file__))


def parse(path):
    """Yield (cmd, {register: [phrasings]}) per block; raise on a bad block."""
    blocks, cur = [], []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.rstrip("\n")
        if line.startswith("#"):
            continue
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append((n, line))
    if cur:
        blocks.append(cur)

    for b in blocks:
        n0, first = b[0]
        if not first.startswith("cmd: "):
            raise ValueError(f"line {n0}: block must start with 'cmd: '")
        cmd = first[len("cmd: "):]
        if not cmd.strip():
            raise ValueError(f"line {n0}: empty cmd")
        if "path/to" in cmd or "$correct" in cmd:
            raise ValueError(f"line {n0}: placeholder in cmd {cmd!r}")
        regs = {}
        for n, line in b[1:]:
            tag, sep, rest = line.partition(": ")
            if tag not in REG or not sep:
                raise ValueError(f"line {n}: expected F:/C:/R:/E:, got {line!r}")
            phr = [p.strip() for p in rest.split(" | ")]
            if any(not p for p in phr):
                raise ValueError(f"line {n}: empty phrasing")
            regs.setdefault(REG[tag], []).extend(phr)
        missing = set(REG.values()) - set(regs)
        if missing:
            raise ValueError(f"line {n0}: {cmd!r} missing {sorted(missing)}")
        yield cmd, regs


def rows(path):
    for i, (cmd, regs) in enumerate(parse(path)):
        for reg, phrs in regs.items():
            for j, nl in enumerate(phrs):
                yield {"id": f"basics:{i}.{j}", "register": reg, "nl": nl, "cmd": cmd}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "basics.txt")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "out", "basics.jsonl")
    out = list(rows(src))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tasks = len({r["id"].split(".")[0] for r in out})
    by = {}
    for r in out:
        by[r["register"]] = by.get(r["register"], 0) + 1
    print(f"{tasks} tasks, {len(out)} rows -> {dst}  " +
          " ".join(f"{k}={v}" for k, v in sorted(by.items())))


if __name__ == "__main__":
    main()

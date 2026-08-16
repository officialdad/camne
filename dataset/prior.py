#!/usr/bin/env python3
"""Fix the pool's tool prior (issue #54). Stdlib only.

  python3 prior.py out/pool_v6.jsonl out/pool_v7.jsonl

pool_v6 is pool_v4.bal + basics.jsonl. Three tuned models answered `nak buat
file baru` with `touch path/to/file1 path/to/file2` or `fossil add`: 14.7%
of rows carry a tldr placeholder in the command, `find` is 17% of the pool
and 4,800 distinct first tokens split the rest. Three rules, in this order:

  placeholders  `path/to/...` and `<name>` in the command. If every one also
                appears verbatim in the NL (the user typed the path), rewrite
                both sides to a concrete name so the pair stays consistent
                and `path/to` leaves the output vocabulary. Otherwise the NL
                never named what the command names — drop. Keystrokes
                (`<Ctrl c>`, `<Enter>`, `<q>`) are not placeholders and stay.
  --cap N       rows per first token for tools outside CORE (rebalance.py's
                list plus every tool basics.txt teaches). Whole pairs are
                sampled, seed 42, so the four registers stay together.
  --find-share  `find` is core and genuinely common, but 17% is a prior no
                task set has; a model that is unsure reaches for it. Sampled
                down to this share of the final pool.

basics.jsonl rows are never dropped. Rewritten commands are the only ones
not byte-identical to source; the rewrite touches nothing but the
placeholder token, and the same token in the NL.
"""
import argparse
import json
import random
import re
from collections import Counter, defaultdict

from basics import parse
from rebalance import CORE, tool

# Shell keywords are not tools; a loop is composition, not a long-tail prior.
KEYWORDS = {"for", "while", "if", "until", "case"}
NAMES = {"file": "notes.txt", "filename": "notes.txt", "directory": "projek",
         "dir": "projek", "folder": "projek"}
KEYS = {"ctrl", "alt", "shift", "esc", "escape", "enter", "return", "space",
        "tab", "backspace", "del", "delete", "up", "down", "left", "right",
        "home", "end", "pageup", "pagedown", "pgup", "pgdn", "super", "cmd",
        "meta", "fn", "insert", "cr"} | {f"f{i}" for i in range(1, 13)}
PATH = re.compile(r"path/to/[\w./-]*\w")
ANGLE = re.compile(r"<[A-Za-z][\w -]+>")   # `<q>`, `<p>` are a key / a tag


def concrete(ph):
    """`path/to/dir_a` -> `dir_a`, `<file>` -> `notes.txt`; None = no safe name."""
    if ph.startswith("<"):
        name = ph[1:-1].split()[0].lower()
        return None if name in KEYS else NAMES.get(name)
    name = ph.rstrip("/").split("/")[-1]
    return NAMES.get(name, name)


def rewrite(nl, cmd):
    """(nl, cmd) with placeholders made concrete, or None to drop."""
    phs = PATH.findall(cmd) + [p for p in ANGLE.findall(cmd)
                               if p[1:-1].split()[0].lower() not in KEYS]
    if any(ph not in nl or concrete(ph) is None for ph in phs):
        return None
    for ph in dict.fromkeys(phs):
        # `/path/to/x` and `path/to/x` alike; `/remote/path/to/x` keeps `/remote/`
        pat = r"(?:(?<![\w/])/)?" + re.escape(ph)
        nl, cmd = re.sub(pat, concrete(ph), nl), re.sub(pat, concrete(ph), cmd)
    if "path/to" in cmd:              # `path/to/*.txt`, `path/to new/dir`
        return None
    return nl, cmd


def sample_ids(rows, keep_rows, seed=42):
    """Deterministic pair-level cut: ids to keep so that ~keep_rows survive."""
    by_id = defaultdict(int)
    for r in rows:
        by_id[r["id"]] += 1
    ids = sorted(by_id)
    random.Random(seed).shuffle(ids)
    kept, n = set(), 0
    for i in ids:
        if n >= keep_rows:
            break
        kept.add(i)
        n += by_id[i]
    return kept


def report(label, rows):
    cnt = Counter(tool(r["cmd"]) for r in rows)
    top30 = sum(n for _, n in cnt.most_common(30))
    ph = sum(1 for r in rows if rewrite(r["nl"], r["cmd"]) != (r["nl"], r["cmd"]))
    print(f"{label}: {len(rows)} rows, {len(cnt)} first tokens, "
          f"top-30 share {100*top30/len(rows):.1f}%, placeholders {ph}, "
          f"find {100*cnt['find']/len(rows):.1f}%")
    return cnt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--cap", type=int, default=300)
    ap.add_argument("--find-share", type=float, default=0.05)
    ap.add_argument("--basics", default="basics.txt")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.src, encoding="utf-8")]
    before = report("before", rows)
    core = set(CORE) | KEYWORDS | {tool(cmd) for cmd, _ in parse(args.basics)}
    hand = lambda r: r["id"].startswith("basics:")

    # 1. placeholders
    kept, rewritten, dropped_ph = [], 0, 0
    for r in rows:
        got = rewrite(r["nl"], r["cmd"])
        if got is None:
            dropped_ph += 1
            continue
        if got != (r["nl"], r["cmd"]):
            rewritten += 1
            r = {**r, "nl": got[0], "cmd": got[1]}
        kept.append(r)
    rows = kept

    # 2. cap the long tail, whole pairs
    by_tool = defaultdict(list)
    for r in rows:
        by_tool[tool(r["cmd"])].append(r)
    keep_ids = set()
    for t in sorted(by_tool):
        rs = by_tool[t]
        if t in core or len(rs) <= args.cap:
            keep_ids.update(r["id"] for r in rs)
        else:
            keep_ids |= sample_ids(rs, args.cap)
    kept = [r for r in rows if hand(r) or r["id"] in keep_ids]
    dropped_cap = len(rows) - len(kept)
    rows = kept

    # 3. find down to --find-share of the final pool
    finds = [r for r in rows if tool(r["cmd"]) == "find" and not hand(r)]
    others = len(rows) - len(finds)
    want = int(others * args.find_share / (1 - args.find_share))
    keep_ids = sample_ids(finds, want) if len(finds) > want else {r["id"] for r in finds}
    kept = [r for r in rows if hand(r) or tool(r["cmd"]) != "find" or r["id"] in keep_ids]
    dropped_find = len(rows) - len(kept)
    rows = kept

    print(f"placeholders: rewrote {rewritten}, dropped {dropped_ph}; "
          f"cap {args.cap}: dropped {dropped_cap}; "
          f"find -> {args.find_share:.0%}: dropped {dropped_find}")
    after = report("after", rows)
    for t in ("find", "touch", "mkdir", "useradd", "tar", "az", "aws", "kubectl",
              "shuf", "fossil", "skicka", "kcadm.sh", "ss", "lsof"):
        print(f"  {t:10s} {before.get(t,0):>7} -> {after.get(t,0):>7}")
    with open(args.dst, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows -> {args.dst}")


if __name__ == "__main__":
    main()

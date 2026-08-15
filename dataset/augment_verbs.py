#!/usr/bin/env python3
"""Fill in Malay verbs the translator never reached for. Stdlib only.

  python3 augment_verbs.py out/pool_v3.train.jsonl out/pool_v3.aug.jsonl

The translated colloquial register has a tic: `tengok` appears 21,268 times
while `cipta` appears twice and `padam` five times, even though "nak padam
file ni" is completely ordinary Malay. A user who reaches for the unlucky
synonym lands off-distribution and the model answers with whatever the long
tail taught it — `zoxide add` for "compress", `git obliterate` for "delete".

So: substitute synonyms into existing rows until every verb in a group clears
a floor, in the registers where that verb is natural. Commands are never
touched, so byte-identity and the scorer are unaffected. Rows are walked in
file order and the first sibling verb wins, so a run is reproducible without
a seed.

This buys coverage, not naturalness — a few substitutions will read slightly
off. That trade is deliberate: the model needs to have *seen* the verb far
more than it needs every row to be idiomatic.
"""
import argparse
import json
import re
import sys
from collections import Counter

# Verbs that mean the same thing to someone at a terminal, and that a
# Malaysian would actually type. English members are listed because rojak and
# colloquial both use them; the register gate below decides which go where.
# `wujudkan`, `papar` and `laksana` are deliberately absent — they are
# formal-register words, the formal rows already carry them, and injecting
# them into colloquial bought 12k rows nobody says out loud.
GROUPS = [
    ["buat", "cipta", "create"],
    ["buang", "padam", "hapus", "delete", "remove"],
    ["salin", "copy"],
    ["pindah", "alih", "move"],
    ["senarai", "list"],
    ["tengok", "tunjuk", "lihat", "check", "show"],
    ["cari", "search", "find"],
    ["tukar", "ubah", "change"],
    ["mampatkan", "compress", "zip"],
    ["nyahmampat", "extract", "unzip"],
    ["pasang", "install"],
    ["jalankan", "run"],
    ["matikan", "hentikan", "kill", "stop"],
    ["buka", "open"],
]

# Malay verbs are natural in both BM registers; English verbs only in rojak,
# which is the register defined by carrying them.
ENGLISH = {"create", "delete", "remove", "copy", "move", "list", "check",
           "show", "search", "find", "change", "compress", "zip", "extract",
           "unzip", "install", "run", "stop", "kill", "open"}


def allowed(verb, register):
    if register == "rojak":
        return True
    if register == "colloquial":
        return verb not in ENGLISH
    return False        # formal keeps the translator's own phrasing


def word(v):
    # Hyphen guards on both sides: plain \b matched inside "dry-run" and
    # turned it into "dry-jalankan".
    return re.compile(r"(?<![-\w])" + re.escape(v) + r"(?![-\w])",
                      re.IGNORECASE)


PATS = {v: word(v) for g in GROUPS for v in g}

# Colloquial openers ("nak", "tolong", "tlg") push the head verb to token 2-3,
# so four tokens is enough to cover it without reaching into the object.
HEAD_TOKENS = 4


def split_head(nl):
    parts = nl.split(" ")
    return " ".join(parts[:HEAD_TOKENS]), " ", " ".join(parts[HEAD_TOKENS:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--floor", type=int, default=3000,
                    help="target rows per verb per register")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.src, encoding="utf-8")]

    have = Counter()
    for r in rows:
        for v, p in PATS.items():
            if p.search(r["nl"]):
                have[(r["register"], v)] += 1

    added, per_verb = [], Counter()
    for group in GROUPS:
        for register in ("colloquial", "rojak"):
            for target in group:
                if not allowed(target, register):
                    continue
                need = args.floor - have[(register, target)]
                if need <= 0:
                    continue
                siblings = [s for s in group if s != target]
                for r in rows:
                    if need <= 0:
                        break
                    if r["register"] != register:
                        continue
                    # Head only. Mid-sentence the same word is usually not a
                    # verb — "compressed file" became "mampatkan file", and
                    # "\0 as line ending" became "create line ending".
                    head, sep, rest = split_head(r["nl"])
                    hit = next((s for s in siblings if PATS[s].search(head)), None)
                    if hit is None:
                        continue
                    nl = PATS[hit].sub(target, head, count=1) + sep + rest
                    if nl == r["nl"]:
                        continue
                    added.append({**r, "id": r["id"] + f"+{target}", "nl": nl})
                    per_verb[(register, target)] += 1
                    need -= 1

    print(f"{len(rows)} rows in, {len(added)} added "
          f"({100*len(added)/len(rows):.1f}%)")
    for (register, v), n in sorted(per_verb.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {register:11s} {v:11s} {have[(register, v)]:6d} -> "
              f"{have[(register, v)] + n:6d}")
    if args.dry_run:
        return
    with open(args.dst, "w", encoding="utf-8") as f:
        for r in rows + added:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows) + len(added)} rows -> {args.dst}")


if __name__ == "__main__":
    sys.exit(main())

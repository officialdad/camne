#!/usr/bin/env python3
"""Prove the command column never drifted from source. Nonzero exit on any
violation. Stdlib only.

  python3 verify.py raw/nl2sh_train.csv out/rows.clean.jsonl
"""
import csv
import json
import os
import sys

REGISTERS = {"formal", "colloquial", "rojak", "english"}


def load_source(path):
    tag = os.path.splitext(os.path.basename(path))[0]
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cmd_col = "bash" if "bash" in reader.fieldnames else reader.fieldnames[1]
        return {f"{tag}:{i}": r[cmd_col] for i, r in enumerate(reader)}


def check(source, rows_path):
    """Returns list of error strings. Split from main for the test."""
    errs = []
    seen = {}
    for n, line in enumerate(open(rows_path, encoding="utf-8"), 1):
        row = json.loads(line)
        rid, reg, cmd = row["id"], row["register"], row["cmd"]
        if reg not in REGISTERS:
            errs.append(f"line {n}: unknown register {reg!r}")
        if rid not in source:
            errs.append(f"line {n}: id {rid} not in source")
        elif cmd != source[rid]:
            errs.append(f"line {n}: command drifted for {rid}: {cmd!r} != {source[rid]!r}")
        if not row.get("nl", "").strip():
            errs.append(f"line {n}: empty nl for {rid}")
        if reg in seen.setdefault(rid, set()):
            errs.append(f"line {n}: duplicate ({rid}, {reg})")
        seen[rid].add(reg)
    for rid, regs in seen.items():
        missing = REGISTERS - regs
        if missing and regs != {"colloquial"}:  # eval-set files are colloquial-only
            errs.append(f"{rid}: missing registers {sorted(missing)}")
    return errs


def main():
    source = load_source(sys.argv[1])
    errs = check(source, sys.argv[2])
    for e in errs[:50]:
        print(e, file=sys.stderr)
    if errs:
        print(f"FAIL: {len(errs)} violations", file=sys.stderr)
        sys.exit(1)
    print(f"ok: {sys.argv[2]} commands byte-identical to {sys.argv[1]}")


if __name__ == "__main__":
    main()

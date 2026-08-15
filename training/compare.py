#!/usr/bin/env python3
"""Paired exact McNemar between two scored answer files. Stdlib only.

  python3 compare.py out/answers_A_bm.jsonl.scored.jsonl out/answers_B_bm.jsonl.scored.jsonl

Same 300 tasks, same scorer; the only pairs that carry information are the
discordant ones (A right, B wrong and vice versa). Exact two-sided binomial p
on those, plus a 95% CI on the pass-rate difference (Wald on paired
proportions). "300 tasks cannot resolve this" is a result: report it.
"""
import json
import math
import sys


def load(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    return {r["index"]: bool(r["pass"]) for r in rows}


def mcnemar(a, b):
    """Return (n, pass_a, pass_b, b_only_wrong, a_only_wrong, p, ci_lo, ci_hi)."""
    keys = sorted(set(a) & set(b))
    n = len(keys)
    pa = sum(a[k] for k in keys)
    pb = sum(b[k] for k in keys)
    lost = sum(1 for k in keys if a[k] and not b[k])    # b lost these
    gained = sum(1 for k in keys if b[k] and not a[k])  # b gained these
    d = lost + gained
    if d == 0:
        p = 1.0
    else:
        k = min(lost, gained)
        p = min(1.0, 2 * sum(math.comb(d, i) for i in range(k + 1)) / 2 ** d)
    diff = (pb - pa) / n
    se = math.sqrt(max(d - (gained - lost) ** 2 / n, 0)) / n
    return n, pa / n, pb / n, lost, gained, p, diff - 1.96 * se, diff + 1.96 * se


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    n, pa, pb, lost, gained, p, lo, hi = mcnemar(a, b)
    print(f"n={n}  A={pa:.3f}  B={pb:.3f}  diff={pb-pa:+.3f}  "
          f"[{lo:+.3f}, {hi:+.3f}]  lost={lost} gained={gained}  p={p:.4g}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        main()
    else:  # self-check: 10 discordant pairs, 9 one way -> p = 2*(1+10)/1024
        a = {i: i < 10 for i in range(20)}
        b = {i: (i < 9) or (i == 19) for i in range(20)}
        n, pa, pb, lost, gained, p, lo, hi = mcnemar(a, b)
        assert (lost, gained) == (1, 1) and p == 1.0, (lost, gained, p)
        b = {i: i < 1 for i in range(20)}
        n, pa, pb, lost, gained, p, lo, hi = mcnemar(a, b)
        assert (lost, gained) == (9, 0) and abs(p - 2 / 512) < 1e-12, (lost, gained, p)
        print("ok")

#!/usr/bin/env python3
"""Score generated answers with the UNMODIFIED InterCode-ALFA scorer.

  uv run eval_score.py --answers out/answers_bm.jsonl

Protocol (PROMPT.md §7.1): eval_mode=embed, threshold 0.75 — needs Ollama
with mxbai-embed-large pulled. Docker required. Per-task results land next
to the input as <answers>.scored.jsonl so a crashed run can be diffed.
"""
import argparse
import json

from icalfa import submit_command


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    ap.add_argument("--eval-mode", default="embed")
    ap.add_argument("--eval-param", default=0.75, type=float)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.answers, encoding="utf-8")]
    score = 0
    with open(args.answers + ".scored.jsonl", "w", encoding="utf-8") as out:
        for n, r in enumerate(rows, 1):
            s = submit_command(index=r["index"], command=r["cmd"],
                               eval_mode=args.eval_mode, eval_param=args.eval_param)
            score += s
            out.write(json.dumps({**r, "pass": s}) + "\n")
            if n % 25 == 0:
                print(f"{n}/{len(rows)}  running pass rate {score / n:.3f}")
    print(f"final: {score}/{len(rows)} = {score / len(rows):.3f}  ({args.answers})")


if __name__ == "__main__":
    main()

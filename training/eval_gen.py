#!/usr/bin/env python3
"""Generate answers for the 300-task eval sets with camne's exact inference
settings (temperature 0, n_predict 64, GBNF single printable line, ChatML) —
mirrors internal/engine/engine.go byte for byte. Stdlib only.

  python3 eval_gen.py --prompts bm  --out out/answers_bm.jsonl
  python3 eval_gen.py --prompts en  --out out/answers_en.jsonl
"""
import argparse
import csv
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = ("You are a shell command generator. Output exactly one line: a "
          "single POSIX/bash command that accomplishes the user's request. "
          "No prose, no markdown fences, no explanation.")
GRAMMAR = "root ::= [ -~]+"  # engine.go:38


def chatml(q):
    return ("<|im_start|>system\n" + SYSTEM + "<|im_end|>\n"
            "<|im_start|>user\n" + q + "<|im_end|>\n"
            "<|im_start|>assistant\n")


def load_prompts(which):
    if which == "en":
        with open(os.path.join(HERE, "../dataset/raw/nl2sh_test.csv"),
                  newline="", encoding="utf-8") as f:
            return [(i, r["nl"]) for i, r in enumerate(csv.DictReader(f))]
    rows = {}
    with open(os.path.join(HERE, "../dataset/eval_bm_300.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows[int(r["id"].split(":")[1])] = r["nl"]
    return sorted(rows.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", choices=("bm", "en"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--endpoint", default="http://127.0.0.1:18092/completion")
    args = ap.parse_args()

    prompts = load_prompts(args.prompts)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as out:
        for i, (index, nl) in enumerate(prompts):
            body = json.dumps({
                "prompt": chatml(nl), "n_predict": 64, "temperature": 0,
                "grammar": GRAMMAR, "cache_prompt": True, "stop": ["\n"],
                "repeat_penalty": 1.08, "repeat_last_n": 64,  # engine.go
            }).encode()
            req = urllib.request.Request(args.endpoint, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                content = json.load(r)["content"].strip()
            cmd = content.splitlines()[0] if content else ""
            out.write(json.dumps({"index": index, "nl": nl, "cmd": cmd},
                                 ensure_ascii=False) + "\n")
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(prompts)}")
    print(f"done -> {args.out}")


if __name__ == "__main__":
    main()

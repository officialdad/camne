#!/usr/bin/env python3
"""Preference pairs from the model's own mistakes (issue #56). Stdlib only.

  python3 dpo_pairs.py                       # -> out/dpo_pairs.jsonl
  python3 dpo_pairs.py --probe out/probe_X.jsonl

SFT teaches what to say; DPO can also teach what not to say. Three kinds of
pair, every one {prompt, chosen, rejected, kind}:

  probe-wrong        probe prompt run 7 failed; chosen = the basics.txt
                     command for that probe task, rejected = what it printed
  probe-placeholder  probe prompt it passed tool-level but answered with a
                     tldr `path/to/...` placeholder; same chosen/rejected rule
  synth-placeholder  every basics.txt row; rejected = the gold with its
                     names swapped for `path/to/file` / `path/to/directory`
  synth-tool-swap    every basics.txt row; rejected = the gold with its tool
                     swapped for an obscure tool that exists in the pool
                     (`fossil add`, `skicka mkdir`, `kcadm.sh` — the ones run 7
                     actually reached for — or one drawn from OBSCURE, seed 42)

Split, stated: ALFA is never touched. Any pair whose prompt is an
eval_bm_300 / eval_rojak_300 / nl2sh_test prompt is dropped (three basics.txt
English phrasings collide with nl2sh_test), so the ALFA numbers stay clean.
The probe is NOT clean after this: probe-* pairs train on the probe's own
prompts, so post-DPO probe basics-task numbers measure recall, not
generalisation. HOLDOUT (no basics.txt command to use as
chosen) and the homograph guard get no pairs and stay clean.
"""
import argparse
import collections
import csv
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "dataset"))
from basics import parse as parse_basics  # noqa: E402

# probe.py task -> the basics.txt command for it, with the probe's own names
# (readme.txt, invoice.pdf, 10.0.0.5 ...) where the prompt carries one.
GOLD = {
    "create file": "touch newfile.txt",
    "create folder": "mkdir newfolder",
    "delete file": "rm notes.txt",
    "list files": "ls",
    "copy file": "cp report.pdf /tmp",
    "rename file": "mv old.txt new.txt",
    "disk space": "df -h",
    "list processes": "ps aux",
    "kill process on port": "kill $(lsof -t -i:8080)",
    "open firewall port": "sudo ufw allow 22",
    "change permission": "chmod +x script.sh",
    "create user": "sudo useradd -m newuser",
    "compress folder": "tar -czf folder.tar.gz folder",
    "search text in files": 'grep -r "error" .',
    "download a url": "wget https://example.com/a.txt",
    "read file": "cat readme.txt",
    "find file by name": "find . -name invoice.pdf",
    "where am i": "pwd",
    "my ip": "ip a",
    "edit file": "nano readme.txt",
    "exit vim": "<Esc>:q<Enter>",
    "exit nano": "<Ctrl x>",
    "extract archive": "tar -xzf data.tar.gz",
    "move file": "mv report.pdf Documents/",
    "count lines": "wc -l data.csv",
    "check internet": "ping -c 4 8.8.8.8",
    "git commit": 'git commit -m "add login"',
    "install package": "sudo apt install htop",
    "run script": "bash deploy.sh",
    "follow log": "tail -f server.log",
    "ram usage": "free -h",
    "ssh into server": "ssh ariff@10.0.0.5",
    "history": "history",
    "empty folder delete": "rmdir temp",
    "copy folder": "cp -r website website_old",
}

# What run 7 actually answered with (probe_qwen-v5, RESULTS.md run 8 table).
KNOWN_SWAP = {
    "touch": "fossil add", "mkdir": "skicka mkdir",
    "useradd": "kcadm.sh create users", "tar": "lzop", "df": "gdu",
    "du": "gdu", "kill": "fkill", "pkill": "fkill", "free": "smem",
    "ps": "jobs", "rmdir": "tempdir -c", "whereis": "whereis -f",
}
# Obscure tools that exist in the pool (asserted against --pool at start).
OBSCURE = ["fossil", "skicka", "kcadm.sh", "fkill", "gdu", "lzop", "smem",
           "abduco", "croc", "duf", "dust", "procs", "tmsu", "xh", "skate",
           "atool", "unar", "lsd", "eza", "bfs"]

DIR_TOOLS = {"mkdir", "rmdir", "cd", "ls", "tree", "du"}
FILE_TOK = re.compile(r"^[\w./-]*\w\.[a-z][a-z0-9]{0,4}$")
HOST_TOK = re.compile(r"\.(com|org|net|io|me|dev|my)$")


def split_tool(cmd):
    """(prefix, tool, rest) — prefix is 'sudo ' or ''; tool is the first word."""
    toks = cmd.split(" ")
    pre = ""
    if toks[0] == "sudo" and len(toks) > 1:
        pre, toks = "sudo ", toks[1:]
    return pre, toks[0], toks[1:]


def placeholder(cmd):
    """Gold with names swapped for path/to/...; None if nothing to swap."""
    pre, tool, rest = split_tool(cmd)
    out, hit = [], False
    for t in rest:
        if t.startswith("-") or "://" in t or HOST_TOK.search(t):
            out.append(t)
        elif t.endswith("/") or (tool in DIR_TOOLS and t[0].isalnum()):
            out.append("path/to/directory")
            hit = True
        elif FILE_TOK.match(t):
            out.append("path/to/file")
            hit = True
        else:
            out.append(t)
    return f"{pre}{tool} {' '.join(out)}".rstrip() if hit else None


def tool_swap(cmd, rng):
    """Gold with its tool replaced by an obscure pool tool; None if no tool."""
    pre, tool, rest = split_tool(cmd)
    if not tool[0].isalpha():   # <Ctrl x>, <Esc>:q<Enter>, `.`, `~`
        return None
    swap = KNOWN_SWAP.get(tool) or rng.choice(OBSCURE)
    return " ".join([swap] + rest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default="out/probe_qwen-v5.jsonl")
    ap.add_argument("--basics", default="../dataset/basics.txt")
    ap.add_argument("--pool", default="../dataset/out/pool_v5.jsonl")
    ap.add_argument("--out", default="out/dpo_pairs.jsonl")
    args = ap.parse_args()
    os.chdir(HERE)

    pool_tools = {split_tool(json.loads(l)["cmd"])[1]
                  for l in open(args.pool, encoding="utf-8")}
    missing = [t for t in OBSCURE if t not in pool_tools]
    assert not missing, f"not in {args.pool}: {missing}"

    pairs = []
    for r in map(json.loads, open(args.probe, encoding="utf-8")):
        if r["task"] not in GOLD:      # holdout / homograph: no gold, stays clean
            continue
        gold = GOLD[r["task"]]
        if r["got"] == gold:
            continue
        if not r["ok"]:
            kind = "probe-wrong"
        elif "path/to" in r["got"]:
            kind = "probe-placeholder"
        else:
            continue
        pairs.append({"prompt": r["prompt"], "chosen": gold,
                      "rejected": r["got"], "kind": kind})

    rng = random.Random(42)
    for cmd, regs in parse_basics(args.basics):
        rej = {"synth-placeholder": placeholder(cmd),
               "synth-tool-swap": tool_swap(cmd, rng)}
        for kind, bad in rej.items():
            if bad and bad != cmd:
                for nl in (p for ps in regs.values() for p in ps):
                    pairs.append({"prompt": nl, "chosen": cmd,
                                  "rejected": bad, "kind": kind})

    # ALFA stays clean: no pair prompt is an eval prompt.
    alfa = set()
    for name in ("eval_bm_300.jsonl", "eval_rojak_300.jsonl"):
        alfa |= {json.loads(l)["nl"].lower()
                 for l in open(f"../dataset/{name}", encoding="utf-8")}
    with open("../dataset/raw/nl2sh_test.csv", newline="", encoding="utf-8") as f:
        alfa |= {r["nl"].lower() for r in csv.DictReader(f)}
    leaked = sorted({p["prompt"] for p in pairs if p["prompt"].lower() in alfa})
    pairs = [p for p in pairs if p["prompt"].lower() not in alfa]
    print(f"dropped {len(leaked)} prompts that are ALFA eval prompts: {leaked}")

    seen, uniq = set(), []
    for p in pairs:
        k = (p["prompt"], p["chosen"], p["rejected"])
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for p in uniq:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    by = collections.Counter(p["kind"] for p in uniq)
    print(f"{len(uniq)} pairs -> {args.out}")
    for k, v in sorted(by.items()):
        print(f"  {k:18s} {v}")


def _selfcheck():
    rng = random.Random(0)
    assert placeholder("touch notes.txt") == "touch path/to/file"
    assert placeholder("mkdir newfolder") == "mkdir path/to/directory"
    assert placeholder("cp notes.txt Documents/") == "cp path/to/file path/to/directory"
    assert placeholder("wget https://example.com/file.zip") is None
    assert placeholder("ls -la") is None
    assert placeholder("ping -c 1 192.168.1.10") is None
    assert placeholder("curl ifconfig.me") is None
    assert placeholder("sudo useradd -m ali") is None
    assert tool_swap("touch newfile.txt", rng) == "fossil add newfile.txt"
    assert tool_swap("sudo useradd -m newuser", rng) == "kcadm.sh create users -m newuser"
    assert tool_swap("<Ctrl x>", rng) is None
    assert split_tool("sudo apt install git") == ("sudo ", "apt", ["install", "git"])


if __name__ == "__main__":
    _selfcheck()
    main()

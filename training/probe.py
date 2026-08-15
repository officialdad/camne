#!/usr/bin/env python3
"""Grid probe: which *phrasing* of the same task does the model survive?

  python3 probe.py                      # shipped model, pinned llama build
  python3 probe.py --model X.gguf

InterCode-ALFA measures whether camne can do a task. This measures whether it
can still do a task it already knows when the user says it a different way —
a different verb, the Malay noun instead of the English one, a count, a
different register. Those are the axes real users vary and the benchmark
holds fixed.

Scoring is tool-level on purpose: "did it reach for touch/mkdir/rm" is coarse,
but it is unambiguous and needs no container, so the whole grid runs in two
minutes and the per-axis breakdown is the actual output. A wrong flag on the
right tool counts as a pass here; ALFA is what catches that.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import time
import urllib.request

SYSTEM = ("You are a shell command generator. Output exactly one line: a "
          "single POSIX/bash command that accomplishes the user's request. "
          "No prose, no markdown fences, no explanation.")
PORT = 18095

PINNED = os.path.expanduser("~/.cache/camne/bin/llama-b10333/llama-server")
MODEL = os.path.expanduser("~/.cache/camne/models/camne-1.5b-Q4_K_M.gguf")

# Each task: the tool that answers it, then the same request in many phrasings.
# axis names are what the report groups by.
TASKS = [
    {
        "task": "create file",
        "ok": r"\b(touch|tee|>\s*\S|printf|cat\s*>)",
        "p": {
            "en": "create a new file",
            "rojak": "nak create file baru",
            "collo-buat-file": "nak buat file baru",
            "collo-buat-fail": "nak buat fail baru",
            "collo-cipta-file": "nak cipta file baru",
            "collo-cipta-fail": "nak cipta fail baru",
            "formal": "Buat satu file baharu",
            "count-en": "create 5 files",
            "count-file": "nak cipta 5 file",
            "count-fail": "nak cipta 5 fail",
        },
    },
    {
        "task": "create folder",
        "ok": r"\bmkdir\b",
        "p": {
            "en": "create a new folder",
            "rojak": "nak create folder baru",
            "collo-buat": "nak buat folder baru",
            "collo-cipta": "nak cipta satu folder",
            "collo-direktori": "nak buat direktori baru",
            "formal": "Buat satu folder baharu",
            "count-en": "create 5 folders",
            "count-bm": "nak buat 5 folder",
        },
    },
    {
        "task": "delete file",
        "ok": r"\b(rm|unlink|shred)\b",
        "p": {
            "en": "delete a file",
            "rojak": "nak delete file ni",
            "collo-buang": "nak buang file ni",
            "collo-padam": "nak padam file ni",
            "collo-fail": "nak buang fail ni",
            "formal": "Hapuskan file tersebut",
        },
    },
    {
        "task": "list files",
        "ok": r"\b(ls|find|dir)\b",
        "p": {
            "en": "list files here",
            "rojak": "nak list file kat sini",
            "collo-tunjuk": "tunjuk semua file kat sini",
            "collo-senarai": "nak senarai semua fail",
            "formal": "Senaraikan semua file dalam folder ini",
        },
    },
    {
        "task": "copy file",
        "ok": r"\b(cp|rsync|install)\b",
        "p": {
            "en": "copy a file to /tmp",
            "rojak": "nak copy file ni ke /tmp",
            "collo-salin": "nak salin file ni ke /tmp",
            "collo-fail": "nak copy fail ni ke /tmp",
            "formal": "Salin file ini ke /tmp",
        },
    },
    {
        "task": "rename file",
        "ok": r"\b(mv|rename)\b",
        "p": {
            "en": "rename a file",
            "rojak": "nak rename file ni",
            "collo-tukar": "nak tukar nama file ni",
            "collo-fail": "nak tukar nama fail ni",
            "formal": "Tukar nama file tersebut",
        },
    },
    {
        "task": "disk space",
        "ok": r"\b(df|du|lsblk)\b",
        "p": {
            "en": "check free disk space",
            "rojak": "nak check disk space",
            "collo-tengok": "nak tengok baki space",
            "collo-cakera": "nak tengok ruang cakera",
            "formal": "Tunjukkan ruang disk yang masih kosong",
        },
    },
    {
        "task": "list processes",
        "ok": r"\b(ps|top|htop|pgrep)\b",
        "p": {
            "en": "list running processes",
            "rojak": "nak list semua process",
            "collo": "tunjuk process yang tengah jalan",
            "formal": "Senaraikan semua process yang sedang berjalan",
        },
    },
    {
        "task": "kill process on port",
        "ok": r"\b(kill|fuser|lsof|pkill|ss)\b",
        "p": {
            "en": "kill the process using port 8080",
            "rojak": "nak kill process guna port 8080",
            "collo": "nak matikan process yang guna port 8080",
            "formal": "Hentikan process yang menggunakan port 8080",
        },
    },
    {
        "task": "open firewall port",
        "ok": r"\b(ufw|firewall-cmd|iptables|nft)\b",
        "p": {
            "en": "open firewall port 22",
            "rojak": "nak open firewall port 22",
            "collo": "nak buka port 22 kat firewall",
            "formal": "Buka port 22 pada firewall",
        },
    },
    {
        "task": "change permission",
        "ok": r"\b(chmod|chown|setfacl)\b",
        "p": {
            "en": "make a file executable",
            "rojak": "nak tukar permission file ni",
            "collo-fail": "nak tukar permission fail ni",
            "collo-keizinan": "nak ubah keizinan file ni",
            "formal": "Tukar permission file tersebut",
        },
    },
    {
        "task": "create user",
        "ok": r"\b(useradd|adduser)\b",
        "p": {
            "en": "create a new user",
            "rojak": "nak create user baru",
            "collo": "nak buat user baru",
            "collo-pengguna": "nak buat pengguna baru",
            "formal": "Buat satu user baharu",
        },
    },
    {
        "task": "compress folder",
        "ok": r"\b(tar|zip|gzip|7z|xz)\b",
        "p": {
            "en": "compress this folder",
            "rojak": "nak compress folder ni",
            "collo-mampat": "nak mampatkan folder ni",
            "formal": "Mampatkan folder ini",
        },
    },
    {
        "task": "search text in files",
        "ok": r"\b(grep|rg|ag|ack|find)\b",
        "p": {
            "en": "search for 'error' in all files",
            "rojak": "nak search 'error' dalam semua file",
            "collo-cari": "nak cari 'error' dalam semua file",
            "collo-fail": "nak cari 'error' dalam semua fail",
            "formal": "Cari perkataan 'error' dalam semua file",
        },
    },
    {
        "task": "download a url",
        "ok": r"\b(curl|wget|aria2c|http)\b",
        "p": {
            "en": "download https://example.com/a.txt",
            "rojak": "nak download https://example.com/a.txt",
            "collo-muat": "nak muat turun https://example.com/a.txt",
            "formal": "Muat turun https://example.com/a.txt",
        },
    },
]

# The homograph guard: `fail` is *file* in Malay and *failure* in English.
# A fix that teaches the Malay sense must not eat the English one.
HOMOGRAPH = [
    ("bm-sense", "nak buat fail baru", r"\b(touch|tee|>\s*\S|printf)"),
    ("bm-sense", "nak buang fail lama", r"\b(rm|unlink|find)\b"),
    ("bm-sense", "nak cari fail besar", r"\b(find|du|ls)\b"),
    ("en-sense", "exit the shell when a command fails", r"set\s+-e|\|\||exit"),
    ("en-sense", "retry the command if it fails", r"until|while|retry|\|\|"),
    ("en-sense", "show only lines where the test failed", r"\b(grep|awk|sed)\b"),
]


def chatml(q):
    return (f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
            f"<|im_start|>user\n{q}<|im_end|>\n<|im_start|>assistant\n")


def ask(q):
    body = json.dumps({"prompt": chatml(q), "n_predict": 64, "temperature": 0,
                       "grammar": "root ::= [ -~]+", "stop": ["\n"],
                       "repeat_penalty": 1.08, "repeat_last_n": 64,
                       "cache_prompt": True}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/completion", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["content"].strip()


def boot(server, model, threads):
    p = subprocess.Popen([server, "-m", model, "-t", str(threads), "-c", "2048",
                          "-ngl", "0", "--no-webui", "--port", str(PORT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.monotonic()
    while True:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            return p
        except Exception:
            if time.monotonic() - t0 > 300:
                p.kill()
                raise RuntimeError("server never became ready")
            time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--server", default=PINNED if os.path.exists(PINNED) else "llama-server")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", default="out/probe.jsonl")
    args = ap.parse_args()

    proc = boot(args.server, args.model, args.threads)
    rows = []
    try:
        for t in TASKS:
            for axis, prompt in t["p"].items():
                got = ask(prompt)
                rows.append({"task": t["task"], "axis": axis, "prompt": prompt,
                             "got": got, "ok": bool(re.search(t["ok"], got))})
        for axis, prompt, ok_re in HOMOGRAPH:
            got = ask(prompt)
            rows.append({"task": "homograph", "axis": axis, "prompt": prompt,
                         "got": got, "ok": bool(re.search(ok_re, got))})
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # group axes into the families we actually want to compare
    def family(axis):
        if axis.startswith("count"):
            return "count"
        if axis in ("en", "rojak", "formal") or axis.startswith("collo"):
            for key in ("fail", "direktori", "pengguna", "cakera", "keizinan",
                        "mampat", "muat", "salin", "padam", "senarai", "cari",
                        "tukar", "buang", "tunjuk", "tengok", "cipta"):
                if axis.endswith(key):
                    return "bm-vocab" if key in (
                        "fail", "direktori", "pengguna", "cakera", "keizinan",
                        "mampat", "muat") else "bm-verb"
            return {"en": "english", "rojak": "rojak",
                    "formal": "formal"}.get(axis, "colloquial")
        return axis

    print(f"\n{len(rows)} prompts, tool-level scoring\n")
    fam = {}
    for r in rows:
        if r["task"] == "homograph":
            continue
        f_ = family(r["axis"])
        fam.setdefault(f_, []).append(r["ok"])
    print(f"{'family':12s} {'pass':>8s}  n")
    for f_, v in sorted(fam.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        print(f"{f_:12s} {sum(v)/len(v):8.2f}  {len(v)}")

    hom = {}
    for r in rows:
        if r["task"] == "homograph":
            hom.setdefault(r["axis"], []).append(r["ok"])
    print(f"\nhomograph guard")
    for a, v in sorted(hom.items()):
        print(f"{a:12s} {sum(v)/len(v):8.2f}  {len(v)}")

    print("\nfailures:")
    for r in rows:
        if not r["ok"]:
            print(f"  [{r['task']}/{r['axis']}] {r['prompt']}\n      => {r['got']}")


if __name__ == "__main__":
    main()

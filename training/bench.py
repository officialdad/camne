#!/usr/bin/env python3
"""Performance on the target box: CPU only, no GPU offload, thread sweep.

  python3 bench.py out/qwen-v2-Q4_K_M.gguf --name camne-qwen

A GPU number would be a lie about the machine camne runs on (4 cores, 8 GB,
no GPU), so this forces `-ngl 0`. Omitting the flag is NOT enough: llama.cpp
defaults `--n-gpu-layers` to `auto` and silently offloads when a GPU exists,
which reads as 200 tok/s instead of 38 and an RSS smaller than the weights.

Reports the metrics the benchmark protocol asks for: tok/s, warm latency
(median of >= 12), cold start, RSS, and size on disk, at 2/4/6/8 threads.

The host CPU is still faster than the 4-core target box, so these are an
upper bound for the machine camne is designed for, not a simulation of it.
"""
import argparse
import json
import os
import re
import signal
import statistics
import subprocess
import time
import urllib.request

SYSTEM = ("You are a shell command generator. Output exactly one line: a "
          "single POSIX/bash command that accomplishes the user's request. "
          "No prose, no markdown fences, no explanation.")
QUERIES = [
    "nak buat file baru", "cari file lagi besar dari 100MB kat folder ni",
    "nak tengok free space", "list semua process", "tolong tunjuk IP address",
    "nak compress folder ni", "tengok 10 baris terakhir log file",
    "cari text 'error' dalam semua file", "nak tukar permission file ni",
    "tunjuk siapa login sekarang", "nak kill process guna port 8080",
    "tengok size folder ni",
]
PORT = 18099


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
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
    return time.monotonic() - t0, d.get("timings", {}).get("predicted_per_second", 0)


def rss_mb(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            return int(re.search(r"VmRSS:\s+(\d+)", f.read()).group(1)) / 1024
    except Exception:
        return 0


def sweep(model, threads):
    proc = subprocess.Popen(
        ["llama-server", "-m", model, "-t", str(threads), "-c", "2048",
         "-ngl", "0", "--no-webui", "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        t0 = time.monotonic()
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except Exception:
                if time.monotonic() - t0 > 300:
                    raise RuntimeError("server never became ready")
                time.sleep(0.5)
        load = time.monotonic() - t0
        cold, _ = ask(QUERIES[0])          # first answer, model already resident
        lat, tps = [], []
        for q in QUERIES:                   # >= 12 queries, median reported
            dt, t = ask(q)
            lat.append(dt)
            tps.append(t)
        return {"threads": threads, "load_s": round(load, 2),
                "cold_s": round(load + cold, 2),
                "warm_s": round(statistics.median(lat), 3),
                "tok_s": round(statistics.median(tps), 1),
                "rss_mb": round(rss_mb(proc.pid))}
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--name", default="")
    ap.add_argument("--threads", default="2,4,6,8")
    args = ap.parse_args()
    name = args.name or os.path.basename(args.model)
    size_mb = round(os.path.getsize(args.model) / 1e6)
    print(f"{name}  ({size_mb} MB on disk, CPU only)")
    print(f"{'threads':>7} {'tok/s':>7} {'warm s':>7} {'cold s':>7} {'RSS MB':>7}")
    rows = []
    for t in [int(x) for x in args.threads.split(",")]:
        r = sweep(args.model, t)
        rows.append(r)
        print(f"{r['threads']:>7} {r['tok_s']:>7} {r['warm_s']:>7} "
              f"{r['cold_s']:>7} {r['rss_mb']:>7}")
    with open(f"out/bench_{name}.json", "w") as f:
        json.dump({"model": name, "size_mb": size_mb, "runs": rows}, f, indent=1)


if __name__ == "__main__":
    main()

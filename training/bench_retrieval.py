#!/usr/bin/env python3
"""Constraint-3 cost of retrieval (issue #55): an embedding server resident
next to the generator, and three `Examples:` lines prepended to the user turn.

  python3 bench_retrieval.py out/qwen-v5-Q4_K_M.gguf out/bge-small-en-v1.5-f16.gguf

CPU only, pinned llama-server, 4 threads (what ships). Reports embed latency
and RSS of the embedding server, then the generator's warm latency / tok/s /
RSS with the baseline prompt and with the retrieval prompt, both servers up.
Same decoding as bench.py. Combined RSS is what constraint 3 gates.
"""
import argparse
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import QUERIES, SYSTEM, rss_mb  # noqa: E402

PINNED = os.path.expanduser("~/.cache/camne/bin/llama-b10333/llama-server")
GEN_PORT, EMB_PORT = 18097, 18098

# Three tldr one-liners in the shape retrieve.py will produce; ~150 tokens
# is the budget the issue names, so pad to that shape rather than the
# shortest lines in the pool.
TLDR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dataset", "raw", "tldr.csv")


def examples(i, k=3):
    """Real retrieval returns different lines per query, so the prompt cache
    covers the system turn only. Rotating one fixed set is not enough: the
    pinned server keeps several evicted prompts in RAM and served the third
    ordering from cache (prompt_n 13, not ~90). Three distinct tldr lines per
    query, 36 in all, no two queries share one."""
    import csv
    rows = [r for r in csv.DictReader(open(TLDR, encoding="utf-8"))
            if 60 <= len(r["nl"]) + len(r["bash"]) <= 110][100:136]
    lines = [f"{r['nl']}: {r['bash']}" for r in rows[3 * i:3 * i + k]]
    return "Examples:\n" + "\n".join(lines) + "\nRequest: "


def wait(port):
    t0 = time.monotonic()
    while True:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return time.monotonic() - t0
        except Exception:
            if time.monotonic() - t0 > 300:
                raise RuntimeError("server never became ready")
            time.sleep(0.2)


def post(port, path, body, timeout=600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ask(q, i=0, k=0):
    prefix = examples(i, k) if k else ""
    prompt = (f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
              f"<|im_start|>user\n{prefix}{q}<|im_end|>\n<|im_start|>assistant\n")
    t0 = time.monotonic()
    d = post(GEN_PORT, "/completion", {
        "prompt": prompt, "n_predict": 64, "temperature": 0,
        "grammar": "root ::= [ -~]+", "stop": ["\n"],
        "repeat_penalty": 1.08, "repeat_last_n": 64, "cache_prompt": True})
    tm = d.get("timings", {})
    return time.monotonic() - t0, tm.get("predicted_per_second", 0), tm.get("prompt_n", 0)


def embed(q):
    t0 = time.monotonic()
    post(EMB_PORT, "/v1/embeddings", {"input": q}, timeout=60)
    return time.monotonic() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gen")
    ap.add_argument("emb")
    ap.add_argument("--server", default=PINNED)
    ap.add_argument("--threads", default="2,4")
    a = ap.parse_args()
    res = [run(a, int(t)) for t in a.threads.split(",")]
    with open("out/bench_retrieval.json", "w") as f:
        json.dump(res, f, indent=1)


def run(a, threads):
    a.threads = threads
    common = ["-t", str(a.threads), "-ngl", "0", "--no-webui"]
    emb = subprocess.Popen([a.server, "-m", a.emb, "--embeddings", "--pooling", "cls",
                            "-c", "512", "-b", "512", "-ub", "512", "--port", str(EMB_PORT)] + common,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    gen = subprocess.Popen([a.server, "-m", a.gen, "-c", "2048", "--port", str(GEN_PORT)] + common,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        emb_load = wait(EMB_PORT)
        gen_load = wait(GEN_PORT)
        embed(QUERIES[0])
        emb_lat = statistics.median(embed(q) for q in QUERIES)
        emb_rss = rss_mb(emb.pid)
        out = {"emb_model": os.path.basename(a.emb), "emb_mb": round(os.path.getsize(a.emb) / 1e6),
               "emb_load_s": round(emb_load, 2), "gen_load_s": round(gen_load, 2),
               "emb_ms": round(emb_lat * 1000, 1), "emb_rss_mb": round(emb_rss), "threads": a.threads}
        for name, k in (("baseline", 0), ("retrieval", 3), ("retrieval_top1", 1)):
            ask(QUERIES[0], 0, k)  # warm the cache
            lat, tps, pn = zip(*(ask(q, i, k) for i, q in enumerate(QUERIES)))
            out[name] = {"warm_s": round(statistics.median(lat), 3),
                         "warm_max_s": round(max(lat), 3),
                         "tok_s": round(statistics.median(tps), 1),
                         "prompt_tokens": int(statistics.median(pn)),
                         "gen_rss_mb": round(rss_mb(gen.pid)),
                         "combined_rss_mb": round(rss_mb(gen.pid) + emb_rss)}
        # end-to-end warm: embed + generate with the longer prompt
        for name in ("retrieval", "retrieval_top1"):
            out[name]["warm_e2e_s"] = round(out[name]["warm_s"] + emb_lat, 3)
        print(json.dumps(out, indent=1))
        return out
    finally:
        for p in (emb, gen):
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=30)


if __name__ == "__main__":
    main()

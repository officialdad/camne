#!/usr/bin/env python3
"""Cosine top-k over tldr one-liners (issue #55).

  python3 retrieve.py                        # builds out/tldr_index.npz if missing
  python3 retrieve.py "nak convert heic ke jpg"

Index: dataset/raw/tldr.csv (nl, bash), deduped, description embedded with
the bge-small GGUF served by the pinned llama-server on EMB_PORT. Lines are
`description: command`, the shape prepended to the user turn as `Examples:`.
"""
import csv
import json
import os
import subprocess
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TLDR = os.path.join(HERE, "..", "dataset", "raw", "tldr.csv")
INDEX = os.path.join(HERE, "out", "tldr_index.npz")
EMB_MODEL = os.path.join(HERE, "out", "bge-small-en-v1.5-f16.gguf")
PINNED = os.path.expanduser("~/.cache/camne/bin/llama-b10333/llama-server")
EMB_PORT = 18098


def serve():
    """Start the embedding server if nothing answers on EMB_PORT."""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{EMB_PORT}/health", timeout=1)
        return None
    except Exception:
        pass
    p = subprocess.Popen([PINNED, "-m", EMB_MODEL, "--embeddings", "--pooling", "cls",
                          "-c", "512", "-b", "512", "-ub", "512", "-t", "4", "-ngl", "0",
                          "--no-webui", "--port", str(EMB_PORT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.monotonic()
    while True:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{EMB_PORT}/health", timeout=1)
            return p
        except Exception:
            if time.monotonic() - t0 > 60:
                raise RuntimeError("embedding server never became ready")
            time.sleep(0.2)


def embed(texts):
    req = urllib.request.Request(f"http://127.0.0.1:{EMB_PORT}/v1/embeddings",
                                 data=json.dumps({"input": texts}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)["data"]
    v = np.array([e["embedding"] for e in sorted(d, key=lambda e: e["index"])], dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def build():
    seen, lines, descs = set(), [], []
    for r in csv.DictReader(open(TLDR, encoding="utf-8")):
        key = (r["nl"], r["bash"])
        if key in seen or not r["nl"] or not r["bash"]:
            continue
        seen.add(key)
        lines.append(f"{r['nl']}: {r['bash']}")
        descs.append(r["nl"])
    vecs = np.concatenate([embed(descs[i:i + 256]) for i in range(0, len(descs), 256)])
    np.savez(INDEX, vecs=vecs.astype(np.float16), lines=np.array(lines))
    return vecs, lines


_IDX = None


def load():
    global _IDX
    if _IDX is None:
        if not os.path.exists(INDEX):
            build()
        z = np.load(INDEX)
        _IDX = (z["vecs"].astype(np.float32), list(z["lines"]))
    return _IDX


def top(query, k=3):
    vecs, lines = load()
    q = embed([query])[0]
    best = np.argsort(vecs @ q)[::-1][:k]
    return [lines[i] for i in best]


def prefix(query, k=3):
    return "Examples:\n" + "\n".join(top(query, k)) + "\nRequest: "


if __name__ == "__main__":
    p = serve()
    try:
        t0 = time.monotonic()
        vecs, lines = load()
        print(f"{len(lines)} lines, {os.path.getsize(INDEX) / 1e6:.1f} MB index, "
              f"loaded in {time.monotonic() - t0:.1f}s")
        for q in sys.argv[1:] or ["nak convert heic ke jpg", "nak tengok certificate expiry",
                                  "convert heic to jpg", "check ssl certificate expiry",
                                  "nak buat file baru", "empty the file app.log without deleting it"]:
            t0 = time.monotonic()
            hits = top(q)
            print(f"\n{q}  ({(time.monotonic() - t0) * 1000:.0f} ms)")
            for h in hits:
                print("  " + h)
    finally:
        if p:
            p.terminate()

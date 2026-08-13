#!/usr/bin/env python3
"""Download source pools into raw/. Stdlib only.

NL2SH-ALFA is public. The whatisit 125,770-row pool is gated on HF —
set HF_TOKEN (and have access to ThorOdinson246/whatisit) or it is skipped.
"""
import os
import sys
import urllib.request

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")

PUBLIC = {
    "nl2sh_train.csv": "https://huggingface.co/datasets/westenfelder/NL2SH-ALFA/resolve/main/train.csv",
    "nl2sh_test.csv": "https://huggingface.co/datasets/westenfelder/NL2SH-ALFA/resolve/main/test.csv",
}

GATED_REPO = "ThorOdinson246/whatisit"


def get(url, dest, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r, open(dest + ".part", "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(dest + ".part", dest)


def main():
    os.makedirs(RAW, exist_ok=True)
    for name, url in PUBLIC.items():
        dest = os.path.join(RAW, name)
        if os.path.exists(dest):
            print(f"ok    {name} (cached)")
            continue
        get(url, dest)
        print(f"ok    {name}")

    token = os.environ.get("HF_TOKEN")
    if not token:
        print(f"skip  {GATED_REPO} pool — set HF_TOKEN and re-run", file=sys.stderr)
        return
    # list files, then fetch anything csv/jsonl/parquet
    import json
    api = f"https://huggingface.co/api/datasets/{GATED_REPO}/tree/main"
    req = urllib.request.Request(api, headers={"Authorization": f"Bearer {token}"})
    try:
        files = json.load(urllib.request.urlopen(req))
    except Exception as e:
        print(f"skip  {GATED_REPO}: {e} (request access on HF?)", file=sys.stderr)
        return
    for f in files:
        path = f["path"]
        if not path.endswith((".csv", ".jsonl", ".parquet", ".json")):
            continue
        dest = os.path.join(RAW, "whatisit_" + path.replace("/", "_"))
        if os.path.exists(dest):
            print(f"ok    {dest} (cached)")
            continue
        get(f"https://huggingface.co/datasets/{GATED_REPO}/resolve/main/{path}", dest, token)
        print(f"ok    {dest}")


if __name__ == "__main__":
    main()

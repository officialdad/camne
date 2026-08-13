#!/usr/bin/env python3
"""English NL→command CSV in, four-register JSONL out. Stdlib only.

Drives a local OpenAI-compatible endpoint (llama-server, vLLM). The command
column is copied byte-identical — this script never touches it; verify.py
proves it.

Resumable: already-emitted (id, register) pairs are skipped on restart.
Unparseable model replies land in <out>.rejects for later retry.

  python3 registers.py --in raw/nl2sh_train.csv --out out/rows.jsonl
  python3 registers.py --in raw/nl2sh_test.csv --out out/eval_bm.jsonl --eval
"""
import argparse
import csv
import json
import os
import re
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

REGISTERS = ("formal", "colloquial", "rojak")

PROMPT = """Translate this English request into MALAYSIAN Bahasa Melayu, in 3 registers. Rules:
- Malaysian BM, NEVER Indonesian. Write Bagaimanakah/memulakan/menyahaktifkan/kod/antara muka — never bagaimana cara/memulai/menonaktifkan/kode/antarmuka/bisa/terhubung.
- Technical nouns STAY ENGLISH: file, folder, directory, delete, download, upload, install, compress, extract, server, list, copy, move, rename, search, permission, process, disk, memory, network, password, user, log, backup, script, command, terminal, port, link, zip, update, restart, bucket, byte, packet, flag, database, output, match, interface, code. Malaysians do not translate these — "S3 bucket" is never "baldi", "port" is never "pelabuhan".
- The meaning must match exactly. Do not add or drop details. Never let a filler word change meaning: "name and PID" is "nama dan PID", never "nama je PID" ("je" means "only").
- Colloquial markers are optional flavour — use them only where a Malaysian naturally would, not in every sentence.
- Output ONLY a JSON object: {"formal": "...", "colloquial": "...", "rojak": "..."}

Registers:
- The user already typed the tool name (`camne`, which means "how do I"), so NO register opens with a "how do I" phrase: never "Bagaimanakah cara untuk", never "camne"/"cmne"/"macam mana"/"mcm mana". Start straight at the request, every register.
- formal: proper written Bahasa Melayu, imperative request: "Paparkan ruang kosong pada semua sistem file.", "Cari file melebihi 100MB dalam folder ini."
- colloquial: how a Malaysian actually types, short and casual: "nak tengok...", "tolong delete...", "cari file...". Vary among: nak, tolong, tlg, boleh tak, tengok, buang. Use kat/ni/tu/je/dah where natural.
- rojak: heavy Malay/English code-switching, keeps whole English phrases ("nak check disk space kat sini"). "lah" is occasional flavour, not a suffix for every sentence.

Request: {nl}"""


def call(endpoint, nl, temperature, timeout):
    body = json.dumps({
        "messages": [{"role": "user", "content": PROMPT.replace("{nl}", nl)}],
        "temperature": temperature,
        "max_tokens": 300,
    }).encode()
    req = urllib.request.Request(endpoint, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = json.load(r)["choices"][0]["message"]["content"]
    # tolerate markdown fences / prose around the JSON object, raw control
    # chars and stray backslashes inside strings — model output, not JSON
    start, end = text.find("{"), text.rfind("}")
    blob = text[start:end + 1]
    try:
        obj = json.loads(blob, strict=False)
    except json.JSONDecodeError:
        obj = json.loads(re.sub(r'\\(?![\\/"bfnrtu])', r"\\\\", blob), strict=False)
    out = {k: " ".join(str(obj[k]).split()) for k in REGISTERS}
    if not all(out.values()):
        raise ValueError("empty register")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--endpoint", default="http://127.0.0.1:8091/v1/chat/completions")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--limit", type=int, default=0, help="translate only the first N rows (smoke test)")
    ap.add_argument("--eval", action="store_true", help="emit colloquial register only (eval-set mode)")
    args = ap.parse_args()

    tag = os.path.splitext(os.path.basename(args.src))[0]
    with open(args.src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cmd_col = "bash" if "bash" in reader.fieldnames else reader.fieldnames[1]
        rows = [(f"{tag}:{i}", r["nl"], r[cmd_col]) for i, r in enumerate(reader)]
    if args.limit:
        rows = rows[:args.limit]

    done = set()
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done.add((r["id"], r["register"]))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    out_f = open(args.out, "a", encoding="utf-8")
    rej_f = open(args.out + ".rejects", "a", encoding="utf-8")
    lock = threading.Lock()
    wanted = ("colloquial",) if args.eval else REGISTERS
    n_done = n_fail = 0

    def work(item):
        nonlocal n_done, n_fail
        rid, nl, cmd = item
        if all((rid, reg) in done for reg in wanted) and (args.eval or (rid, "english") in done):
            return
        try:
            tr = call(args.endpoint, nl, args.temperature, timeout=120)
        except Exception:
            try:  # one retry
                tr = call(args.endpoint, nl, args.temperature, timeout=120)
            except Exception as e:
                with lock:
                    n_fail += 1
                    rej_f.write(json.dumps({"id": rid, "nl": nl, "err": str(e)}) + "\n")
                return
        emit = [{"id": rid, "register": reg, "nl": tr[reg], "cmd": cmd} for reg in wanted]
        if not args.eval:
            emit.append({"id": rid, "register": "english", "nl": nl, "cmd": cmd})
        with lock:
            for row in emit:
                if (row["id"], row["register"]) not in done:
                    out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n_done += 1
            if n_done % 100 == 0:
                out_f.flush()
                print(f"{n_done} translated, {n_fail} rejected", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, rows))
    out_f.close()
    rej_f.close()
    print(f"done: {n_done} translated, {n_fail} rejected ({args.out})")


if __name__ == "__main__":
    main()

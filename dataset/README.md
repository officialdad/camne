# dataset pipeline — milestone 5

English NL→command pairs in, four-register BM rows out. Commands are never
touched: byte-identity is checked, not assumed.

Stdlib-only Python 3 (mirrors the repo's no-dependency rule). No venv needed.

## Flow

```
fetch.py      # source pools → raw/           (NL2SH-ALFA public; whatisit pool needs HF_TOKEN + access)
registers.py  # raw CSV → out/rows.jsonl      (drives a local LLM endpoint, resumable)
stoplist.py   # out/rows.jsonl → out/rows.clean.jsonl  (force technical nouns back to English, marker stats)
verify.py     # asserts every command byte-identical to source; nonzero exit on drift
```

Eval set (300 InterCode-ALFA prompts, colloquial only):

```
python3 registers.py --in raw/nl2sh_test.csv --out out/eval_bm.jsonl --eval
python3 stoplist.py out/eval_bm.jsonl out/eval_bm.clean.jsonl   # eval gets stoplisted too
```

Hand review sample:

```
shuf -n 200 out/rows.clean.jsonl | python3 -c "import json,sys; [print(json.loads(l)['register'],'|',json.loads(l)['nl']) for l in sys.stdin]"
```

Reads like a government circular → pipeline broken, fix before scaling.

## Row schema

```json
{"id": "nl2sh:1042", "register": "colloquial", "nl": "camne nak cari file lagi besar dari 100MB", "cmd": "find . -size +100M"}
```

`register` ∈ formal | colloquial | rojak | english. `cmd` byte-identical to
source, all four rows. Optional `target` field (shell/OS context line) is
tolerated by verify.py but not generated — decision pending (issue #1).

## Translation route

Local LLM on the 3090 via any OpenAI-compatible endpoint (llama-server or
vLLM), `--endpoint http://127.0.0.1:8091/v1/chat/completions`. No external
API: no terms-on-derived-datasets problem, nothing to record in NOTICE beyond
the model licence, and the whole 125k run is free.

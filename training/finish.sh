#!/bin/bash
# Post-training pipeline: merged bf16 -> f16 GGUF -> Q4_K_M -> eval answers.
# Scoring is separate (needs docker + the embed shim); see score.sh.
#
#   ./finish.sh out/qwen-lora-merged qwen
#
# CONVERT points at a llama.cpp checkout holding convert_hf_to_gguf.py.
set -euo pipefail
MERGED=${1:?usage: finish.sh <merged-dir> <name>}
NAME=${2:?usage: finish.sh <merged-dir> <name>}
CONVERT=${CONVERT:-$HOME/.claude/jobs/c0339307/tmp/llamacpp/convert_hf_to_gguf.py}
PORT=${PORT:-18092}
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

echo "== convert to f16 GGUF"
PYTHONPATH="$(dirname "$CONVERT")/gguf-py" \
  uv run python "$CONVERT" "$MERGED" --outfile "out/$NAME-f16.gguf" --outtype f16

echo "== quantize Q4_K_M"
llama-quantize "out/$NAME-f16.gguf" "out/$NAME-Q4_K_M.gguf" Q4_K_M

echo "== generate eval answers"
llama-server -m "out/$NAME-Q4_K_M.gguf" -ngl 99 --port "$PORT" -c 4096 >"out/$NAME-server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 60); do
  curl -s "http://127.0.0.1:$PORT/health" | grep -q ok && break
  sleep 2
done
python3 eval_gen.py --prompts en --out "out/answers_${NAME}_en.jsonl" --endpoint "http://127.0.0.1:$PORT/completion"
python3 eval_gen.py --prompts bm --out "out/answers_${NAME}_bm.jsonl" --endpoint "http://127.0.0.1:$PORT/completion"

echo "== spot check"
for q in "nak buat file baru" "nak delete image docker" "nak exit vim" "cari file lagi besar dari 100MB kat folder ni"; do
  printf '%s => ' "$q"
  python3 - "$q" "$PORT" <<'PY'
import json, sys, urllib.request
SYS = ("You are a shell command generator. Output exactly one line: a single "
       "POSIX/bash command that accomplishes the user's request. No prose, no "
       "markdown fences, no explanation.")
q, port = sys.argv[1], sys.argv[2]
p = f"<|im_start|>system\n{SYS}<|im_end|>\n<|im_start|>user\n{q}<|im_end|>\n<|im_start|>assistant\n"
body = json.dumps({"prompt": p, "n_predict": 64, "temperature": 0,
                   "grammar": "root ::= [ -~]+", "stop": ["\n"],
                   "repeat_penalty": 1.08, "repeat_last_n": 64}).encode()
req = urllib.request.Request(f"http://127.0.0.1:{port}/completion", data=body,
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=180) as r:
    print(json.load(r)["content"].strip())
PY
done

ls -la "out/$NAME-Q4_K_M.gguf"
echo "done — score with: bash score.sh $NAME"

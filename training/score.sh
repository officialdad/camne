#!/bin/bash
# Score generated answers with the unmodified InterCode-ALFA scorer.
# Needs docker. The embed shim replaces an ollama install: same mxbai F16
# weights, served by llama-server, on the URL the scorer hardcodes.
#
#   ./score.sh qwen                     # scores out/answers_qwen_{en,bm}.jsonl
#   ./score.sh ""                       # scores the untuned baseline
#   ./score.sh qwen out/answers_x.jsonl # ...plus any extra files, same server
set -euo pipefail
NAME=${1-}
SUFFIX=${NAME:+_$NAME}
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
EMBED_MODEL=${EMBED_MODEL:-$HOME/.cache/camne-dataset/mxbai-embed-large-v1_fp16.gguf}

llama-server -m "$EMBED_MODEL" --embeddings --port 18093 -ngl 99 >out/embed.log 2>&1 &
EMBED=$!
python3 embed_shim.py >out/shim.log 2>&1 &
SHIM=$!
trap 'kill $EMBED $SHIM 2>/dev/null || true' EXIT
for _ in $(seq 30); do
  curl -s http://127.0.0.1:18093/health | grep -q ok && break
  sleep 2
done

uv run eval_score.py --answers "out/answers${SUFFIX}_en.jsonl"
uv run eval_score.py --answers "out/answers${SUFFIX}_bm.jsonl"
# Extra answer files scored inside the same embed-server lifetime; starting a
# second one per file is minutes of model load for nothing.
shift || true
for extra in "$@"; do
  uv run eval_score.py --answers "$extra"
done

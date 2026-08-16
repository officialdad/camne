#!/bin/bash
# One arm, end to end: train -> GGUF -> answers (en, bm, rojak) -> probe -> score -> bench.
#
#   setsid nohup ./rebuild.sh qwen-v5 ../dataset/out/pool_v5.jsonl > out/rebuild-qwen-v5.log 2>&1 &
#
# One variable per run, seed 42 (train.py). Third arg picks the train.py base
# (default qwen, the incumbent), fourth the seed (issue #57: repeat a run
# under seeds 43/44 to measure the noise floor). Third arg `dpo` runs dpo.py
# instead with the second arg as the pairs file (issue #56):
#
#   setsid nohup ./rebuild.sh qwen-v5-dpo out/dpo_pairs.jsonl dpo > out/rebuild-qwen-v5-dpo.log 2>&1 &
#   DPO_BASE=out/X-lora-merged ./rebuild.sh X-dpo out/dpo_pairs.jsonl dpo   # on top of another SFT run
#
# Read RESULTS.md before starting one: the hypothesis goes there first, as
# something that could come back false.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
NAME=${1:?usage: rebuild.sh <name> <pool.jsonl> [base]}
POOL=${2:?usage: rebuild.sh <name> <pool.jsonl> [base]}
BASE=${3:-qwen}
SEED=${4:-42}
rm -f "out/REBUILD_DONE_$NAME"
status() { echo "rebuild[$NAME]: $*"; }

status "train (1 epoch, seed $SEED, $(wc -l <"$POOL") rows, base $BASE)"
if [ "$BASE" = dpo ]; then
  uv run dpo.py --base-ckpt "${DPO_BASE:-out/qwen-v5-lora-merged}" --data "$POOL" --out "out/$NAME-lora"
else
  uv run train.py --base "$BASE" --seed "$SEED" --epochs 1 --data "$POOL" --out "out/$NAME-lora"
fi || { echo "DONE rebuild:train-failed" >"out/REBUILD_DONE_$NAME"; exit 1; }

status "convert + quantize + generate en/bm answers"
./finish.sh "out/$NAME-lora-merged" "$NAME" || { echo "DONE rebuild:convert-failed" >"out/REBUILD_DONE_$NAME"; exit 1; }

status "rojak answers (finish.sh only does en + bm)"
PORT=18092
llama-server -m "out/$NAME-Q4_K_M.gguf" -ngl 99 --port $PORT -c 4096 >"out/$NAME-rojak-server.log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for _ in $(seq 60); do curl -s "http://127.0.0.1:$PORT/health" | grep -q ok && break; sleep 2; done
python3 eval_gen.py --prompts rojak --out "out/answers_${NAME}_rojak.jsonl" \
  --endpoint "http://127.0.0.1:$PORT/completion"
kill $SRV 2>/dev/null || true; wait $SRV 2>/dev/null || true

status "probe (CPU, pinned llama build — what actually ships)"
python3 probe.py --model "out/$NAME-Q4_K_M.gguf" --out "out/probe_$NAME.jsonl" \
  >"out/probe_$NAME.txt" 2>&1 || true
tail -40 "out/probe_$NAME.txt" || true

status "score"
./score.sh "$NAME" "out/answers_${NAME}_rojak.jsonl" || true

status "bench"
python3 bench.py "out/$NAME-Q4_K_M.gguf" --name "$NAME" || true

echo "DONE rebuild:trained" >"out/REBUILD_DONE_$NAME"
status "complete"

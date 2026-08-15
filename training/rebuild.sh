#!/bin/bash
# Run 5: the register-aware pool. Train -> GGUF -> probe -> eval -> score.
#
#   setsid nohup ./rebuild.sh > out/rebuild.log 2>&1 &
#
# The BM eval set changed with the pipeline fix (80 of 300 rows now carry
# Malay nouns instead of English ones), so run 4 is re-scored on the new set
# too. Comparing run 5's new-set score against run 4's old-set score would be
# measuring the yardstick, not the model.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
NAME=qwen-v3
POOL=../dataset/out/pool_v3.bal.jsonl
SHIPPED="$HOME/.cache/camne/models/camne-1.5b-Q4_K_M.gguf"
rm -f out/REBUILD_DONE
status() { echo "rebuild: $*"; }

status "train (1 epoch, $(wc -l <"$POOL") rows)"
uv run train.py --base qwen --epochs 1 --micro-batch 4 --grad-accum 8 \
  --data "$POOL" --out "out/$NAME-lora" || { echo "DONE rebuild:train-failed" >out/REBUILD_DONE; exit 1; }

status "convert + quantize + generate answers"
./finish.sh "out/$NAME-lora-merged" "$NAME" || { echo "DONE rebuild:convert-failed" >out/REBUILD_DONE; exit 1; }

status "rojak answers (finish.sh only does en + bm)"
PORT=18092
llama-server -m "out/$NAME-Q4_K_M.gguf" -ngl 99 --port $PORT -c 4096 >"out/$NAME-rojak-server.log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for _ in $(seq 60); do curl -s "http://127.0.0.1:$PORT/health" | grep -q ok && break; sleep 2; done
python3 eval_gen.py --prompts rojak --out "out/answers_${NAME}_rojak.jsonl" \
  --endpoint "http://127.0.0.1:$PORT/completion"

status "re-score run 4 on the rebuilt BM set (baseline parity)"
kill $SRV 2>/dev/null || true; wait $SRV 2>/dev/null || true
llama-server -m "$SHIPPED" -ngl 99 --port $PORT -c 4096 >out/run4-server.log 2>&1 &
SRV=$!
for _ in $(seq 60); do curl -s "http://127.0.0.1:$PORT/health" | grep -q ok && break; sleep 2; done
python3 eval_gen.py --prompts bm --out "out/answers_run4new_bm.jsonl" \
  --endpoint "http://127.0.0.1:$PORT/completion"
kill $SRV 2>/dev/null || true; wait $SRV 2>/dev/null || true

status "probe (CPU, pinned llama build — what actually ships)"
python3 probe.py --model "out/$NAME-Q4_K_M.gguf" --out "out/probe_$NAME.jsonl" \
  >"out/probe_$NAME.txt" 2>&1 || true
tail -30 "out/probe_$NAME.txt" || true

status "score"
./score.sh "$NAME" "out/answers_${NAME}_rojak.jsonl" "out/answers_run4new_bm.jsonl" || true

status "bench"
python3 bench.py "out/$NAME-Q4_K_M.gguf" --name "$NAME" || true

echo "DONE rebuild:trained" >out/REBUILD_DONE
status "complete"

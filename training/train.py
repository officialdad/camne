#!/usr/bin/env python3
"""LoRA tune, adapted for the RTX 3090 per issue #2.

One arm per invocation, one variable at a time, seed 42:

  uv run train.py --base qwen
  uv run train.py --base sealion

Recipe is the whatisit-validated one: r32/a64/dropout 0.05, all-linear,
2e-4 cosine 3% warmup, 2 epochs, packing off, seq 512, effective batch 32.
Unsloth is an implementation-level speedup only — bf16 LoRA, NOT QLoRA
(a quantized base would be a second changed variable).

The chat template uses the exact system prompt from internal/engine/engine.go —
training format must match what the CLI sends at inference.
"""
import argparse
import json
import os

from unsloth import FastLanguageModel  # must be imported before transformers
from datasets import Dataset
from trl import SFTConfig, SFTTrainer

# byte-for-byte the systemPrompt const in internal/engine/engine.go
SYSTEM = ("You are a shell command generator. Output exactly one line: a "
          "single POSIX/bash command that accomplishes the user's request. "
          "No prose, no markdown fences, no explanation.")

BASES = {
    "qwen": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "sealion": "aisingapore/Gemma-SEA-LION-v4.5-E2B-IT",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", choices=BASES, required=True)
    ap.add_argument("--data", default="../dataset/out/pool.train.jsonl")
    ap.add_argument("--out", default=None)
    ap.add_argument("--micro-batch", type=int, default=16,
                    help="drop this and raise --grad-accum if OOM; keep the product 32")
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--epochs", type=float, default=2,
                    help="four registers per command means 1 epoch is already "
                         "4 exposures; 2 overfits on a narrow pool")
    args = ap.parse_args()
    out = args.out or f"out/{args.base}-lora"

    model, tokenizer = FastLanguageModel.from_pretrained(
        BASES[args.base], max_seq_length=512, dtype=None, load_in_4bit=False,
    )
    model = FastLanguageModel.get_peft_model(
        model, r=32, lora_alpha=64, lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth", random_state=42,
    )

    def to_text(row):
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": row["nl"]},
                {"role": "assistant", "content": row["cmd"]}]
        return {"text": tokenizer.apply_chat_template(msgs, tokenize=False)}

    rows = [json.loads(l) for l in open(args.data, encoding="utf-8")]
    ds = Dataset.from_list(rows).shuffle(seed=42).map(to_text)
    print(f"{len(ds)} rows from {args.data}")

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=ds,
        dataset_text_field="text",
        args=SFTConfig(
            output_dir=out,
            per_device_train_batch_size=args.micro_batch,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=args.epochs,
            learning_rate=2e-4,
            lr_scheduler_type="cosine",
            warmup_ratio=0.03,
            packing=False,
            max_seq_length=512,
            bf16=True,
            seed=42,
            logging_steps=25,
            save_strategy="epoch",
            report_to="none",
        ),
    )
    trainer.train()

    # merged bf16 checkpoint; GGUF f16 -> Q4_K_M conversion is a separate step
    model.save_pretrained_merged(out + "-merged", tokenizer, save_method="merged_16bit")
    print(f"merged model at {out}-merged")


if __name__ == "__main__":
    main()

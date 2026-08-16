#!/usr/bin/env python3
"""DPO stage on top of a merged SFT checkpoint (issue #56).

  uv run dpo.py                                   # run 7 merged -> out/qwen-v5-dpo-lora
  uv run dpo.py --base-ckpt out/X-lora-merged --data out/dpo_pairs.jsonl --out out/X-dpo-lora
  ./finish.sh out/qwen-v5-dpo-lora-merged qwen-v5-dpo

One variable vs the SFT run it sits on: this stage. Fresh LoRA (same
r32/a64/all-linear as train.py) on the merged checkpoint, TRL DPOTrainer,
sigmoid loss, beta 0.1, 1 epoch, seed 42, effective batch 32. Reference
model is the same weights with the adapter disabled (TRL's default for
PEFT), so no second copy in VRAM. bf16 LoRA, not QLoRA.

Pairs come from dpo_pairs.py: {prompt, chosen, rejected}. The prompt is
wrapped in the same literal ChatML as train.py; chosen/rejected are the bare
commands and TRL appends eos (<|im_end|> for Qwen) itself, so the training
text is byte-identical in shape to the SFT rows.
"""
import argparse
import json

from unsloth import FastLanguageModel, PatchDPOTrainer  # before transformers
from datasets import Dataset
from trl import DPOConfig, DPOTrainer

from train import CHATML, SYSTEM

PatchDPOTrainer()
PROMPT = CHATML.split("{cmd}")[0]   # ChatML up to and including "assistant\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-ckpt", default="out/qwen-v5-lora-merged")
    ap.add_argument("--data", default="out/dpo_pairs.jsonl")
    ap.add_argument("--out", default="out/qwen-v5-dpo-lora")
    ap.add_argument("--micro-batch", type=int, default=8,
                    help="DPO holds chosen+rejected+ref per row; keep the product 32")
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--lr", type=float, default=5e-6,
                    help="Unsloth's DPO reference recipe; SFT's 2e-4 would wreck the policy")
    args = ap.parse_args()

    model, tokenizer = FastLanguageModel.from_pretrained(
        args.base_ckpt, max_seq_length=192, dtype=None, load_in_4bit=False,
    )
    model = FastLanguageModel.get_peft_model(
        model, r=32, lora_alpha=64, lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth", random_state=42,
    )

    rows = [json.loads(l) for l in open(args.data, encoding="utf-8")]
    ds = Dataset.from_list([{
        "prompt": PROMPT.format(sys=SYSTEM, nl=r["prompt"]),
        "chosen": r["chosen"], "rejected": r["rejected"],
    } for r in rows]).shuffle(seed=42)
    print(f"{len(ds)} pairs from {args.data}")

    trainer = DPOTrainer(
        model=model, ref_model=None, processing_class=tokenizer, train_dataset=ds,
        args=DPOConfig(
            output_dir=args.out,
            beta=0.1,
            loss_type="sigmoid",
            per_device_train_batch_size=args.micro_batch,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=1,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            warmup_ratio=0.03,
            max_prompt_length=128,
            max_completion_length=64,
            max_length=192,
            bf16=True,
            seed=42,
            logging_steps=10,
            save_strategy="epoch",
            report_to="none",
        ),
    )
    trainer.train()

    # merged bf16 checkpoint; finish.sh takes it from here
    model.save_pretrained_merged(args.out + "-merged", tokenizer, save_method="merged_16bit")
    print(f"merged model at {args.out}-merged")


if __name__ == "__main__":
    main()

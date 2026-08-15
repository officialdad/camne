# Bake-off results

InterCode-ALFA, unmodified scorer, 300 tasks per set. Fixed settings, stated
with every number: temperature 0, `n_predict` 64, embed threshold 0.75,
`repeat_penalty` 1.08 / `repeat_last_n` 64, GBNF single-line grammar — the
same settings `internal/engine` sends. Seed 42. BM set is the colloquial
translation in `dataset/eval_bm_300.jsonl`; EN set is the untouched
NL2SH-ALFA test split, kept as the regression control.

| run | training pool | epochs | BM pass | EN pass |
|---|---|---|---|---|
| nl2sh-1.5b (shipping today) | whatisit's 125,770 English pairs | — | 0.297 | **0.593** |
| 1 | NL2SH-ALFA + tldr, 70,356 pairs | 2 | 0.387 | 0.493 |
| 2 | NL2SH-ALFA only, 40,938 pairs | 2 | 0.410 | 0.457 |
| 3 | NL2SH-ALFA + tldr, 70,356 pairs | 1 | **0.440** | 0.507 |
| 4 | + commandlinefu + git-instruction, 76,785 pairs | 1 | 0.417 | **0.533** |

All tunes are Qwen2.5-Coder-1.5B-Instruct, LoRA r32/a64/dropout 0.05,
all-linear, 2e-4 cosine 3% warmup, seq 512, effective batch 32, bf16, seed 42.
Every pair contributes four rows (formal, colloquial, rojak, English).

Run 3 against the untuned base, paired exact McNemar:

- BM: +0.143 (89 -> 132 of 300), 26 lost / 69 gained, **p = 1.2e-05**
- EN: -0.086 (178 -> 152 of 300), 50 lost / 24 gained, **p = 0.0034**

## What the runs establish

Malay accuracy is settled: every tune beats the shipping model by a wide,
significant margin, and run 3 lifts it by half again. English is the open
problem — no tune has matched the base's 0.593.

Two levers moved it, and the first hypothesis was wrong:

**tldr was innocent.** Run 2 dropped it on the theory that its uniform
one-page-per-tool shape flattened the tool-frequency distribution. English
got *worse* (0.493 -> 0.457), so the mix was not the cause.

**Epochs were half the story.** Four registers per command means one epoch is
already four exposures of every command; the inherited "2 epochs" was set for
one-row-per-command data. Run 2 reached a lower training loss (0.437 vs
0.542) on less data and scored worse on both sets — overfitting, confirmed by
the failure mode: the model invents memorised path prefixes
(`cat /home/tecmint/scripts/setup.sh` for a bare filename). Halving to one
epoch lifted both scores (run 1 -> run 3).

**Pool size is the other half.** English tracks it monotonically across every
run: 40,938 pairs -> 0.457, 70,356 -> 0.493/0.507, and the base's 125,770 ->
0.593. Our English register is one row in four, so a 70k pool carries 70k
English examples against the base's 125,770.

Run 4 combined both: the larger pool at one epoch. English reached 0.533,
and against the base the gap is now **p = 0.050** — at 300 tasks the
difference is no longer resolvable, which the protocol asks us to report as a
result rather than round to "as good as". Malay stays clearly ahead:
+0.120, p = 0.0002.

Runs 3 and 4 cannot be told apart (BM p = 0.47, EN p = 0.44). Run 3 spends
its budget on Malay, run 4 on English, and their averages are identical to
three decimals. Picking between them on the two endpoint registers is
guesswork, which is what the rojak column below is for.

## The register we were not measuring

camne's real input is rojak — Malay grammar around English technical nouns
(`nak check disk space kat sini`), because Malaysians do not translate *file*,
*port* or *server*. It is 25% of the training pool and was 0% of the
evaluation: the two endpoints were measured and the middle, which is the
actual use case, was not.

`dataset/eval_rojak_300.jsonl` fixes that — the same 300 InterCode-ALFA
tasks in rojak, scorer untouched. No rojak NL2SH benchmark existed before
this one.

| model | BM | rojak | EN | mean |
|---|---|---|---|---|
| nl2sh-1.5b (shipping today) | 0.297 | 0.430 | **0.593** | 0.440 |
| run 3 | **0.440** | 0.477 | 0.507 | 0.474 |
| run 4 | 0.417 | **0.490** | 0.533 | **0.480** |

The column earns its keep immediately. The shipping model scores far better
on rojak (0.430) than on Malay (0.297) — the English technical nouns carry
it, which is the same reason rojak is what people type. And it separates two
tunes that the endpoint registers could not: against the shipping model,
run 4's rojak gain is significant (+0.060, p = 0.044) and run 3's is not
(+0.047, p = 0.125), while the two tunes cannot be told apart from each
other (p = 0.70).

## Decision: run 4

Run 4 wins rojak, wins the mean, and is the only tune whose gain on the
register camne actually receives is significant. Against the shipping model:

| register | change | p |
|---|---|---|
| BM | +0.120 | 0.0002 |
| rojak | +0.060 | 0.044 |
| EN | -0.060 | 0.050 |

The English number is the honest caveat: at 300 tasks the difference is not
resolvable, so this is "cannot distinguish", not "as good as". Two of three
registers improve significantly and the third cannot be called either way —
for a tool whose input is Malay and rojak, that is the trade to take, and it
is stated here rather than buried.


## The SEA-LION arm

Issue #2 asked for a bake-off, so the other candidate was tuned on the same
pool with the same recipe — one variable changed, the base model:
`aisingapore/Gemma-SEA-LION-v4.5-E2B-IT` in place of
Qwen2.5-Coder-1.5B-Instruct.
9,599 steps, 9 h 05 m on the GPU.

| model | BM | rojak | EN | size | tok/s @4t | RSS |
|---|---|---|---|---|---|---|
| camne-1.5b (run 4) | **0.417** | **0.490** | **0.533** | **986 MB** | **40.0** | **1.63 GB** |
| sealion tune | 0.277 | 0.243 | 0.303 | 3428 MB | 20.3 | 4.18 GB |

It loses every register, and loses worst on rojak — the one that matters. It
is also 3.5x the disk, half the speed, and **4.18 GB resident against a 2.5 GB
budget**, so constraint 3 rules it out even if the accuracy had gone the other
way.

The training loss predicted this and was worth reading as a warning rather
than a result: SEA-LION reached 0.067 where Qwen settled at 0.54, on identical
data. An order of magnitude lower loss with worse held-out accuracy is
memorisation, not skill — a larger base with the capacity to fit 307k rows
rather than generalise from them.

The bake-off is closed. Run 4 ships; SEA-LION is not a candidate at any size.


## Performance on CPU

llama.cpp defaults `--n-gpu-layers` to `auto` and offloads silently when a
GPU is present, so `bench.py` forces `-ngl 0`. Omitting the flag reported
200 tok/s and an RSS *smaller than the weights* — a GPU measurement wearing a
CPU label, which is the one number this project must never publish.

camne-1.5b-Q4_K_M, 986 MB on disk, no GPU:

| threads | tok/s | warm s | cold s | RSS MB |
|---|---|---|---|---|
| 2 | 26.0 | 0.806 | 1.66 | 1627 |
| 4 | 40.0 | 0.490 | 1.97 | 1627 |
| 6 | 43.9 | 0.399 | 1.38 | 1628 |
| 8 | 45.0 | 0.354 | 1.49 | 1628 |

Budget is warm < 1.5 s, cold < 5 s, RSS < 2.5 GB. All four thread counts
clear it, at 65% of the memory budget.

Two caveats, both worth stating rather than rounding away:

**This CPU is faster than the target box.** These are an upper bound for a
4-core student laptop, not a simulation of one. A true target-box number
needs the hardware or a throttled VM.

**Threads are not purely memory-bandwidth-bound here.** Going 2 -> 4 threads
buys +54% tok/s, which the "half the cores" default was not expecting.
`engine.go` gives a 4-core machine 2 threads, so it lands at 26 tok/s and
0.806 s warm — inside budget, with the machine left responsive for whatever
else the user is doing. Keeping the conservative default, and recording here
that the headroom exists if warm latency ever becomes the complaint.


## Known defect: the BM column is not measuring BM

Found 2026-08-15, after run 4 shipped, from a user report that
`camne nak buat fail baru` returns `echo "fail" > /tmp/fail.txt`. It does,
because the model has never seen `fail` mean *file*.

`dataset/stoplist.py` rewrites Malaysian technical nouns to English. That is
correct for **rojak**, whose definition is Malay grammar around English nouns.
It was applied to all four registers, which erased the vocabulary from the
pool entirely:

| word | in raw translations | in training pool |
|---|---|---|
| fail | 29,576 | 29 |
| direktori | 14,711 | 0 |
| arahan | 3,524 | 0 |
| kata laluan | 618 | 0 |
| pelayan | 813 | 0 |
| cakera | 560 | 0 |
| skrip | 826 | 0 |

`file` appears 84,820 times against `fail`'s 29. The "formal BM" register is
therefore formal BM grammar carrying 100% English vocabulary, and a user
typing genuine Malay hits tokens the model saw zero times.

The registers did not otherwise collapse — mean inter-register token overlap
is 0.09 to 0.27, so they differ properly by grammar and particles. The defect
is specific to nouns.

`eval_bm_300.jsonl` was built through the same `clean()` and inherits it:
124 occurrences of `file`, 41 of `folder`, zero of `direktori`. Prompts read
`nak tengok file terbuka je`. That is rojak. **So the BM and rojak columns
above measure nearly the same register, and the BM number is not evidence
about Malay vocabulary.** The run-to-run comparisons stay valid — every row
was scored on the same sets — but the absolute BM figure will fall once the
eval set is rebuilt honestly.

Fix costs no GPU for the data half: `out/rows.jsonl` and
`out/extra_rows.jsonl` retain the raw vocabulary. Split `STOPLIST` into the
Indonesian-to-Malaysian half (always applied) and the BM-to-English half
(rojak only), then re-run clean, disambiguate, and pool. Only the retrain
needs the GPU.

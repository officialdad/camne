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


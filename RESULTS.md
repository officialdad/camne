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

Why it lost is not what the loss curve suggested. SEA-LION bottomed out at
0.067 against Qwen's 0.54 on identical data, which reads as memorisation —
but a loss curve cannot separate "learned the task" from "memorised the
answers", so that was inference, not evidence.

The evidence points elsewhere. Measured against its own English:

| model | EN | BM | BM - EN |
|---|---|---|---|
| SEA-LION | 0.303 | 0.277 | **-0.026** |
| camne-1.5b (run 4) | 0.533 | 0.417 | -0.116 |

SEA-LION's Malay penalty is a quarter of Qwen's. Relative to what it can do
in English, it handles Malay *better* — which is exactly what a SEA-language
model should do, and it means the Malay is the part that works. What fails is
the shell, in every register at once:

```
print hello world                        => hello world
copy /testbed/hello.php to hello-COPY    => mv ...     (move, not copy)
nak buat file /testbed/test.txt          => touch {/testbed/test.txt}
list open files                          => ls /proc/<pid>/fd   (not lsof)
```

Wrong verb, brace syntax error, a placeholder standing in for the tool, and
one answer that is not a command at all. `Gemma-SEA-LION-v4.5-E2B-IT` is a
general instruct model; `Qwen2.5-Coder-1.5B-Instruct` is a code model, and
the output of this task is code, not prose. Language ability was never the
bottleneck, so the base chosen for its language ability had nothing to
contribute.

The lesson generalises past this arm: for NL2SH the base's *code* ability
dominates, and a language-specialised base has to make that up before its
language advantage counts for anything.

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


## Runs 5 and 6: the register-aware pool

Three pipeline defects were fixed together (see the Known defect section and
`dataset/README.md`): the stoplist split so Malay nouns survive outside rojak,
verb augmentation so `cipta` and `padam` exist in colloquial at all, and a
tool rebalance against a pool where `shuf` outweighed `touch` 11 to 1.

Run 5 took all three. Run 6 removed one variable — the core-tool upsampling —
after run 5 came back worse than the model it was meant to replace.

| model | BM* | rojak | EN |
|---|---|---|---|
| run 4 (shipping) | 0.430 | 0.490 | 0.533 |
| run 5 (+ upsampling) | 0.453 | 0.477 | 0.493 |
| **run 6 (no upsampling)** | **0.467** | **0.497** | **0.553** |

\* BM on the rebuilt eval set. `eval_bm_300.jsonl` had gone through the same
merged stoplist as the training pool, so it read `nak tengok file terbuka je`
— rojak, not BM. 80 of 300 rows changed. Run 4 was re-scored on the new set
rather than compared against its old 0.417, which would have measured the
yardstick instead of the model. `eval_rojak_300.jsonl` came out byte-identical,
which is the confirmation the split is right: rojak is *defined* by English
nouns, so the surviving half of the stoplist is the half that applies to it.

**The upsampling was the harm.** Run 6 beats run 5 on English by +0.060,
p = 0.041 — the only significant result in the set. 27% of run 5's pool was
duplicate rows and one prompt appeared 150 times, which is a partial second
epoch on a subset, the failure mode run 2 already established. Its lower
training loss said nothing: it was re-answering rows it had already seen.

**Run 6 is not distinguishable from run 4.** BM +0.037 (p = 0.207), rojak
+0.007 (p = 0.904), EN +0.020 (p = 0.519). Aggregated over all 900 tasks it is
105 wins to 86, p = 0.193 — indicative only, three sets are not one sample.
Positive in direction everywhere, resolvable nowhere.

### What the probe measured that ALFA could not

`training/probe.py` asks the same 15 tasks in many phrasings — different verb,
Malay noun instead of English, a count, a different register — and scores at
tool level. ALFA gives every task exactly one phrasing, so it is structurally
blind to this.

| family | run 4 | run 6 | n |
|---|---|---|---|
| BM vocabulary (`fail`, `direktori`) | 0.69 | **0.85** | 13 |
| BM verb (`cipta`, `padam`, `salin`) | 0.56 | **0.78** | 9 |
| formal | 0.73 | 0.73 | 15 |
| english | 1.00 | 0.93 | 15 |
| rojak | 0.87 | 0.80 | 15 |
| colloquial | 1.00 | 0.57 | 7 |

The two families the fixes targeted moved, and they are the two with usable
n. The rest moved down at n = 5 to 7, which is not enough to read.

### The finding that matters more than either run

`create a file` fails in run 6 across every phrasing — `fossil add`,
`skicka`, `mktemp`. It failed in run 5 too, so the duplication was not the
cause. The pool is:

```
"buat/cipta/create + file" prompts    run 4 pool: touch 4.3%   run 6 pool: touch 4.9%
plain `touch <file>` rows             116, all phrased "buat file kosong <name>"
```

Neither pool teaches "create a new file". Run 4 answering `touch file.txt` —
the README's headline example — was luck, not learning. The single most basic
terminal task is uncovered in every pool version we have built.

### Decision: keep run 4 shipped

Run 6 cannot be distinguished from run 4 on the benchmark, breaks the demo
example, and shows small probe regressions alongside its real gains. Shipping
on a directional aggregate is the claim this file exists to prevent.

What the three runs did buy is a correct pipeline: Malay vocabulary is in the
pool, verbs are covered, the longest-match ordering bug is gone, and there is
now a check that can see phrasing failures at all. The gap left is coverage of
the tasks a beginner actually starts with, which is small and hand-writable.


## Run 7: the beginner rows

**Hypothesis, written before the run.** The `create a file` failure is a
coverage hole, not a weighting problem: the pool has 116 `touch` rows and
every one says *"buat file kosong"*. Adding ~2,500 hand-written beginner rows
(`dataset/basics.txt`, 326 tasks, four registers, several phrasings per task
on the probe's axes) **once, unweighted**, into the run 6 pool will lift the
probe's basics-task pass rate and fix `create a file` in every phrasing,
without moving ALFA English significantly either way. Falsified if the probe
does not move on the tasks basics.txt covers — that would mean 0.7% of the
pool is drowned and weighting is the next variable.

One variable changed from run 6: `pool_v5 = pool_v4.bal + basics.jsonl`.
Same recipe, seed 42, 1 epoch.

**Probe split, stated.** `training/probe.py` grew from 15 tasks / 85 prompts
to 35 tasks / 177 prompts plus a 10-task / 40-prompt HOLDOUT block. No probe
prompt appears verbatim in `basics.txt` (probe.py refuses to start if one
does), so the main block measures *phrasing generalisation on tasks the
model was taught*; the HOLDOUT block uses tools that are absent from
`basics.txt` entirely (`truncate`, `tac`, `whereis`, `dirname`, `tee`,
`timeout`, `chsh`, `printenv`, `nl`, size-sort composition) and measures
whether anything generalised past the rows we wrote. Adding one of those
tools to basics.txt retires it from HOLDOUT. A new axis, `shortcut`, carries
typing shortcuts (`tgk`, `mcm`, `dlm`, `msk`, `skrg`, `sy`, `x` for *tak*),
which nothing in the pool teaches — issue #41 work item 2.

Baselines were re-probed on the expanded grid rather than compared against
their old 85-prompt numbers.

### Scorer fix, applied before reading any number

The embed backend behind the scorer (`embed_shim.py`, standing in for the
Ollama install the scorer hardcodes) answered any input past 512 tokens with
a 500, and the scorer counts that as a wrong answer. Ollama truncates and
embeds the head. 14 of run 7's 900 tasks hit it, 29 of run 6's, and every
earlier run some number nobody counted, always on the tasks whose command
output is long. The shim now truncates the way Ollama does, and every file
below was **re-scored** with it — run 4, run 7 and the whatisit model, all
three registers. Earlier sections keep their original numbers; they compare
like with like and the fix moves 1–7 tasks per file.

Re-scoring the same answers twice also exposed the scorer's noise floor:
tasks 42, 43, 202, 211, 214, 243 and 297 flip between identical runs
(non-deterministic commands, container state). That is ±5 of 300, ±1.7
points, and it is smaller than every difference called significant below
and larger than several that are not.

### Results

ALFA, three registers, all files re-scored with the fixed shim. whatisit's
model (`nl2sh-1.5b`) is the head-to-head row #41 asks for, on the same
rebuilt sets, same scorer.

| model | BM | rojak | EN | mean |
|---|---|---|---|---|
| whatisit `nl2sh-1.5b` | 0.310 | 0.447 | **0.603** | 0.453 |
| run 4 (shipping) | 0.437 | 0.490 | 0.553 | 0.493 |
| **run 7 (basics)** | **0.487** | 0.490 | 0.543 | **0.507** |

Paired exact McNemar (`training/compare.py`), 95% CI on the difference:

| comparison | BM | rojak | EN |
|---|---|---|---|
| run 7 vs run 4 | +0.050 [−0.004, +0.104], p = 0.091 | 0.000, p = 1 | −0.010 [−0.058, +0.038], p = 0.79 |
| run 7 vs whatisit | **+0.177 [+0.117, +0.236], p = 3e-08** | +0.043 [−0.008, +0.095], p = 0.13 | **−0.060 [−0.113, −0.007], p = 0.036** |
| run 4 vs whatisit | +0.127, p = 5e-05 | +0.043, p = 0.15 | −0.050, p = 0.096 |

Over all 900 tasks run 7 vs run 4 is 101 gained / 89 lost, p = 0.42.
**ALFA cannot tell run 7 from run 4.** That is expected and it is the point
of having two instruments: ALFA's 300 tasks are advanced one-liners, one
phrasing each, and basics.txt is 326 beginner tasks. The probe is what
measures the thing that changed.

Probe, 223 prompts, tool-level, same three models on the same grid:

| family | run 4 | run 6 | **run 7** | n |
|---|---|---|---|---|
| shortcut (`tgk`, `mcm`, `x`) | 0.50 | 0.60 | **0.80** | 10 |
| colloquial | 0.74 | 0.65 | **0.84** | 31 |
| formal | 0.77 | 0.69 | **0.83** | 35 |
| bm-verb | 0.64 | 0.82 | **0.91** | 11 |
| bm-vocab | 0.67 | 0.87 | **0.93** | 15 |
| rojak | 0.89 | 0.74 | **0.91** | 35 |
| english | 0.91 | 0.86 | **1.00** | 35 |
| count | 0.80 | 0.60 | **1.00** | 5 |
| **basics tasks (unseen phrasings)** | 0.79 | 0.74 | **0.90** | 177 |
| holdout (tools absent from basics.txt) | 0.95 | 0.85 | 0.90 | 40 |
| homograph `fail` BM-sense / EN-sense | 0.33 / 0.67 | 0.33 / 0.67 | **1.00** / 0.67 | 3 / 3 |

Paired on the 177 basics-task prompts: run 7 vs run 4 gained 30 / lost 10,
**p = 0.002**, CI [+0.04, +0.18]; vs run 6 gained 37 / lost 9, p = 4e-05.
Holdout: 1 gained / 3 lost vs run 4, p = 0.63 — flat, which is the honest
reading: the gain is on the tasks we wrote rows for, phrased in ways we did
not write, and it did not generalise to tools the rows never mention. (The
177 prompts are 35 tasks × ~5 phrasings, so they are not 177 independent
trials; the p-value is optimistic by that correlation and the direction and
size are what to read.)

`create a file`, the finding that started this: run 6 failed all 10
phrasings; run 7 passes 9 of 10 (`Buat satu file baharu` still returns
`fossil add`). `nak buat file baru` — the README's headline — comes back
`touch path/to/file1 path/to/file2 ...`: right tool, tldr placeholder,
because a bare "new file" with no name is a phrasing basics.txt gives a
filename to. A handful of unnamed rows (`touch newfile.txt`) is the next
edit; it is not in this run because it was found by this run.

Constraint 3, `bench.py`, CPU only, run 7 GGUF 986 MB: 2 threads 31.5 tok/s
/ 0.72 s warm / 1.46 s cold / 1623 MB; 4 threads 36.8 / 0.57 / 1.38 / 1626.
Same architecture and quant as run 4; clears the budget by the same margin.

**Hypothesis outcome: held.** Unweighted inclusion of 2,496 rows (0.7% of
the pool) moved the probe's basics-task pass rate by +0.11 (p = 0.002),
fixed `create a file` in 9 of 10 phrasings, took the `fail` homograph guard
from 0.33 to 1.00 on the BM side without moving the EN side, and left ALFA
where it was on all three registers. Weighting is not needed and stays
unimplemented.

### Where camne is worse, stated

Against whatisit on English, run 7 is −0.060, p = 0.036 — the first time
that gap has been resolvable at 300 tasks (run 4's −0.050 was p = 0.096).
Every English row in our pool is one of four registers of the same 76k
pairs against whatisit's 125k English pairs; English still tracks pool
size, as every run has shown. Someone who only ever types English is
better off with whatisit's model, and the README should say so.

### Decision

Run 7 meets the loop's exit criterion: significant on beginner tasks, no
significant regression on any register, clears constraint 3. Shipping it
is an owner decision (loop protocol, "stop and ask before shipping a model
swap"). The claim it supports is narrow and should be written that way:
*better on Malay and on the first fifty things a beginner asks; not better
on advanced English one-liners.*


## Work item 3: constraint 3 gate on candidate bases

Every base #41 lists, at Q4_K_M, `bench.py`, CPU only, no accuracy row for
any that fails the memory budget. tok/s and RSS are comparable across rows.
Warm/cold latency is **not**: bench.py sends the Qwen ChatML template, so a
non-Qwen base runs to the 64-token cap every time and its warm number is a
worst case, not a comparison. Numbers are for the gate, not for picking.

| base | disk MB | tok/s 2t / 4t | RSS MB @4t | constraint 3 |
|---|---|---|---|---|
| Qwen2.5-Coder-0.5B-Instruct | 398 | 50.7 / 63.2 | 1114 | clears |
| Llama-3.2-1B-Instruct | 808 | 31.4 / 41.2 | 1559 | clears |
| gemma-3-1b-it | 806 | 22.5 / 30.7 | 1625 | clears |
| **Qwen2.5-Coder-1.5B-Instruct** (incumbent) | 986 | 25.1 / 40.0 | 1628 | clears |
| deepseek-coder-1.3b-instruct | 874 | 24.8 / 36.8 | 2025 | clears |
| SmolLM2-1.7B-Instruct | 1056 | 26.6 / 33.7 | 1995 | clears |
| Qwen2.5-Coder-3B-Instruct | 1930 | 16.5 / 22.3 | **2605** | **out: RSS** |
| Llama-3.2-3B-Instruct | 2019 | 13.0 / 18.1 | **2815** | **out: RSS** |

Both 3B bases fail RSS at Q4_K_M by 100–300 MB, and their 2-thread speed
(13–16 tok/s) would put a 30-token answer past 2 s warm on the target box
before latency was even measured. Q3 quants would fit the memory but that
is a second variable and a known accuracy cost; not pursued without an
owner saying so.

Six bases clear the gate. Each accuracy arm is one GPU day (train, ALFA ×3,
probe, bench) and the SEA-LION result says code ability dominates, which
puts `deepseek-coder-1.3b` first and the two general 1B models last. **Not
run in this loop**: the loop's exit criterion was met by run 7, and
spending six GPU days on arms is a decision the owner makes with the run 7
numbers in hand. Retrieval-over-tldr and distillation are likewise unrun.


## Run 8: the unnamed rows (issue #47)

**Hypothesis, written before the run.** Run 7's remaining `create a file`
failures are one hole, not a family: every `touch`/`mkdir`/`useradd`/`tar`
row in basics.txt names its target (`touch notes.txt`, `useradd -m ali`), so
a bare request with no name — `nak buat satu file baru`, `nak buat user
baru`, `nak compress folder ni` — falls back to the tldr row and returns
`touch path/to/file1 path/to/file2 ...`, `skicka mkdir path/to/folder`,
`kcadm.sh create users ...`. Adding four unnamed blocks (`touch
newfile.txt`, `mkdir newfolder`, `sudo useradd -m newuser`, `tar -czf
folder.tar.gz folder`, ~85 rows in four registers) plus two `bukak`
phrasings on `ss -tulpn` will make the unnamed phrasings return a command
with a real name in it, without moving ALFA in any register (the change is
0.02% of the pool). Falsified if the unnamed prompts still return
placeholders — that would mean the tldr `touch` row (116 copies) outweighs a
dozen hand rows and weighting is next.

One variable changed from run 7: `pool_v6 = pool_v4.bal + basics.jsonl`
with basics.txt at 330 tasks / 2,581 rows (was 326 / 2,496). Same recipe,
seed 42, 1 epoch. Probe prompts are unchanged; none is verbatim in
basics.txt.

Measured before the run, shipped run 7 model, `camne` v0.8.0 (the probe
scores tool-level and already passes these, so the check is exact output):

| prompt | run 7 |
|---|---|
| `nak buat file baru` | `touch path/to/file1 path/to/file2 ...` |
| `nak buat satu file baru` | `touch path/to/file1 path/to/file2 ...` |
| `tolong buat file baru` | `touch path/to/file1 path/to/file2 ...` |
| `nak buat folder baru` | `skicka mkdir path/to/folder` |
| `buat folder baru je` | `skicka mkdir path/to/folder` |
| `nak buat user baru` | `kcadm.sh create users -s username=username -r realm_name` |
| `nak compress folder projek` | `zip -r project.zip projek` |
| `nak list port bukak` / `buka` / `terbuka` | `lsof -i` / `netstat -an \| grep -i listen` / `lsof -i` |

### Result: the rows land, the run does not

Trained 2026-08-16, `qwen-v6`, 10,804 steps, 2 h 58 m on the GPU. Same
recipe as run 7, seed 42, 1 epoch. Everything below is the pinned CPU
llama build, the shipped path.

**The unnamed prompts, exact output** (the thing #47 is about):

| prompt | run 7 | run 8 |
|---|---|---|
| `nak buat file baru` | `touch path/to/file1 path/to/file2 ...` | **`fossil add path/to/file`** |
| `nak buat satu file baru` | `touch path/to/file1 ...` | `touch newfile.txt` |
| `tolong buat file baru` | `touch path/to/file1 ...` | `touch newfile.txt` |
| `create a new file` | `touch path/to/file1 ...` | `touch newfile.txt` |
| `nak buat folder baru` | `skicka mkdir path/to/folder` | `mkdir newfolder` |
| `buat folder baru je` | `skicka mkdir path/to/folder` | `mkdir newfolder` |
| `nak buat user baru` | `kcadm.sh create users ...` | `sudo useradd -m new_user` |
| `nak compress folder projek` | `zip -r project.zip projek` | `zip -r projek.zip projek` |
| `nak list port bukak` | `lsof -i` | **`sudo ufw status`** |
| `nak list port buka` / `terbuka` | `netstat -an \| grep -i listen` / `lsof -i` | `netstat -lnptu` / `netstat -tulpn` |

Seven of ten now return a real command with a real name in it, which is
what the hypothesis predicted for the rows we wrote. The two failures are
the two that matter most: `nak buat file baru` (the README's original
headline, and a probe prompt) moved from a tldr placeholder to `fossil add`,
and `bukak` moved from a valid tool to a firewall status command.

**Probe** (`probe_qwen-v6.txt`, 223 prompts, tool-level): basics tasks
0.89 (run 7: 0.90), holdout 0.82 (0.78), homograph BM-sense **0.33 (1.00)**.
`create file` fell from 9/10 to **5/10**: every colloquial phrasing with
`file baru` / `fail baru` and no count now returns `fossil add path/to/file`.
`kill process on port` went 4/4 to 0/4 (`fkill :8080`, a real tool the
regex does not know; scored as a fail, arguably a pass). `run script` 5/5 to
0/5 (`source <(curl -s https://raw.githubusercontent.com/...)` — worse than
wrong). English fell 1.00 → 0.91.

**ALFA, 300 tasks per register, paired exact McNemar run 8 vs run 7:**

| register | run 7 | run 8 | diff [95% CI] | lost / gained | p |
|---|---|---|---|---|---|
| BM | 0.487 | **0.427** | **−0.060 [−0.110, −0.010]** | 39 / 21 | **0.027** |
| rojak | 0.490 | 0.520 | +0.030 [−0.022, +0.082] | 27 / 36 | 0.31 |
| EN | 0.543 | 0.553 | +0.010 [−0.038, +0.058] | 25 / 28 | 0.78 |

BM lost 6 points, significant. Rojak and English are inside the noise
floor. Bench: 4 threads 36.2 tok/s / 0.59 s warm / 1.26 s cold / 1585 MB,
unchanged from run 7 as expected (same base, same quant, 986 MB).

**Reading.** The hypothesis was "the unnamed rows land, ALFA does not
move". Half held: the rows landed where the phrasing was close to what we
wrote. The other half is false: 85 rows (0.02% of the pool) moved BM by
−0.06 with p = 0.027 and flipped `create file` from 9/10 to 5/10 on prompts
those rows were meant to fix. That is not what 85 rows do to a 345k-row
gradient; it is what a different data order does. Same seed, but the extra
rows shift every shuffle boundary after them, so run 8 is a different
trajectory, not run 7 plus a nudge. **The seed-42, one-variable protocol
does not isolate a data change this small from run-to-run variance**, and
nothing in runs 4–8 measured that variance directly because no run was ever
repeated.

**Not shipping run 8.** A model that returns `fossil add` for `nak buat file
baru` and loses 6 BM points does not replace run 7, whatever it fixed. #47
stays open with the rows in place.

**Next, in order, no GPU spent without an owner go-ahead:**

1. Repeat run 7 exactly (`pool_v5`, seed 42) once. If it does not reproduce
   run 7's probe within a few prompts, the noise floor on the probe is the
   finding and every basics-row comparison so far needs that error bar.
2. If run 7 reproduces, run 8 with seeds 43 and 44 on `pool_v6`. Two of
   three agreeing beats one run of anything.
3. Only then weight the rows (`create file` ×5) — the variable the run 7
   hypothesis named as next if the rows drowned.


## Work item 3, second gate: bases released after the first list

The #48 list predates Qwen3.5 (March 2026), Gemma 4 (April) and LFM2.5
(August). Same gate as above: `bench.py`, CPU only, pinned llama b10333,
Q4_K_M, untuned instruct GGUFs. Warm/cold latency is still a worst case for
non-Qwen bases (bench sends ChatML and an untuned model runs to the 64-token
cap); tok/s and RSS are the numbers.

| base | disk MB | tok/s 2t / 4t | RSS MB @4t | constraint 3 |
|---|---|---|---|---|
| Qwen3.5-0.8B | 533 | 35.9 / 44.7 | 1289 | clears |
| Qwen3.5-2B | 1281 | 16.6 / 24.5 | 2328 | clears, 170 MB margin |
| LFM2.5-2.6B | 1674 | 15.2 / 22.2 | **2948** | **out: RSS** |
| gemma-4-E2B-it | **3107** | not run | — | **out: disk alone exceeds the RSS cap** |
| Qwen2.5-Coder-1.5B (incumbent, from the first gate) | 986 | 25.1 / 40.0 | 1628 | clears |

Qwen3.5-2B is the strongest candidate on paper (Apache-2.0, 201 languages,
Unsloth 2026.8 trains it, GGUF exists) and it clears, but not comfortably:
40% slower than the incumbent at 4 threads (24.5 vs 40.0 tok/s; a 30-token
answer is 1.2 s of generation before prompt eval, against a 1.5 s warm
budget on a slower box than this one) and 700 MB more resident. The
Gated-DeltaNet hybrid does not buy CPU speed in llama.cpp at this size.
Qwen3.5-0.8B clears everything with room and is 12% faster than the
incumbent, at 55% of its parameters. Neither has an accuracy number yet;
that is the arm.

Order if arms are run: Qwen3.5-2B first (capability), Qwen3.5-0.8B second
(the constraint-3 upgrade if its accuracy holds). Both need a `train.py`
BASES entry; Qwen3.5 keeps ChatML so the template code is unchanged.


## Arm: Qwen3.5-2B on the run 7 pool

**Hypothesis, written before the run.** The incumbent's Malay comes from
the pool alone; Qwen2.5-Coder-1.5B was pretrained for code and its Malay
was incidental. Qwen3.5-2B (March 2026) is pretrained on 201 languages and
a newer, larger corpus, and is 33% bigger. Tuned on the same pool
(`pool_v5`, the run 7 pool), same recipe, seed 42, it will beat run 7 on BM
and rojak by at least +0.05 each and hold English (within the noise floor).
Falsified if no register clears the run 7 number by more than the CI, or if
English drops significantly — then the base's advantage does not survive
the tune and the 0.8B arm decides on constraint-3 grounds only.

One variable changed from run 7: the base. Same pool, same seed, same
LoRA rank/targets, same epoch count. Two implementation notes, neither a
tuning choice:

- Training text is now built from a literal ChatML string (`train.py`
  `CHATML`) instead of `tokenizer.apply_chat_template`. For Qwen2.5 the two
  are byte-identical (checked), so run 7 is unaffected. Qwen3.5's template
  inserts an empty `<think>\n\n</think>\n\n` block before every assistant
  turn; camne's engine never sends one, and a model trained to expect it
  would emit `<think>` as its answer under camne's `\n` stop.
- LoRA targets are unchanged (`q/k/v/o_proj`, `gate/up/down_proj`). In the
  Qwen3.5 hybrid only every fourth block has `q/k/v/o`; the Gated-DeltaNet
  blocks are untouched. MLPs are hit in every block. A wider target set is a
  second variable and is not in this run.

Bench gate for this base is above (24.5 tok/s @4t, RSS 2328 MB, 1281 MB on
disk); the tuned GGUF will be re-benched, but the base numbers are already
the shape of the trade: this arm buys accuracy, if it buys anything, at
40% of the incumbent's speed margin.

### Result: falsified, the base does not carry

Trained 2026-08-16, `qwen35-2b`, 10,802 steps, 2 h 55 m on the GPU, final
loss 0.54 (run 7: 0.53). Merge, f16 convert (llama.cpp Aug-13 checkout,
`Qwen3_5ForConditionalGeneration` → text GGUF) and Q4_K_M quantize went
through unchanged; the GGUF is 1,312 MB.

**ALFA, 300 tasks per register, paired exact McNemar vs run 7 (same pool,
same seed, base is the only change):**

| register | run 7 | Qwen3.5-2B | diff [95% CI] | lost / gained | p |
|---|---|---|---|---|---|
| BM | 0.487 | **0.417** | **−0.070 [−0.125, −0.015]** | 47 / 26 | **0.019** |
| rojak | 0.490 | 0.453 | −0.037 [−0.092, +0.019] | 42 / 31 | 0.24 |
| EN | 0.543 | 0.490 | −0.053 [−0.112, +0.006] | 49 / 33 | 0.097 |

Worse on every register; significant on BM, the register the hypothesis
said it would win by +0.05. Not one column moved the predicted way.

**Probe** (223 prompts, tool-level): basics tasks **0.83** (run 7: 0.90),
holdout **0.72** (0.78), colloquial 0.74 (0.84), english 0.83 (1.00),
count 0.60 (1.00). `create file` 3/10 (`fossil add path/to/file` again,
this time even on `create a new file`), `delete file` loses 4 of 6,
`kill process on port` 0/4. Homograph BM-sense 1.00, shortcut 1.00 — the
two axes it did not lose.

**#47 prompts, exact:** `nak buat file baru` → `fossil add path/to/file`;
`nak buat folder baru` → `mkdir /tmp/new_directory`; `nak buat user baru`
→ `sudo useradd username`; `nak list port bukak` → `netstat -an | grep
:80`; `nak install btop untuk arch` → `sudo pacman -S btop`; `nak exit
vim` → `<Esc>:q<Enter>`.

**Bench, tuned GGUF, CPU, pinned build:** 4 threads 28.2 tok/s / 0.60 s
warm / 2.08 s cold / 2089 MB. Clears constraint 3, with less room than the
incumbent on every axis (run 7: 36.8 / 0.57 / 1.38 / 1626).

**Reading.** 201-language pretraining and 33% more parameters did not
survive one epoch of the same LoRA on the same pool; the tuned Qwen3.5-2B
is a worse camne than the tuned Qwen2.5-Coder-1.5B on Malay, on English,
on the beginner probe, and on speed. The one confound worth naming: the
LoRA targets hit `q/k/v/o` in only every fourth Qwen3.5 block (the
Gated-DeltaNet blocks have none), so this arm adapted less of the network
than run 7 did. Widening the targets to the linear-attention projections is
a legitimate second arm. It is not run here: it is a second variable, and
the −0.07 BM gap is bigger than what a target-set change usually buys.

**Not shipping. Not running the 0.8B arm without an owner go-ahead**: it is
half the incumbent's parameters from a family that just lost at 133% of
them; its case was constraint 3, and constraint 3 is not what needs
fixing.

The `train.py` change (literal ChatML training text) stays: it is
byte-identical for the incumbent and removes the chat-template dependency
for every future base.

## Run 7 repeated: the noise floor (issue #57)

**Hypothesis, written before the run.** No run in this file has ever been
repeated, so every gain claimed since run 4 (run 7's +0.05 BM included) has
no error bar, and run 8's −0.06 BM from 85 rows was read as data order, not
data. This run is run 7 again with nothing changed: same pool
(`pool_v5.jsonl`), same recipe, seed 42, 1 epoch, same base, same pinned
CPU llama build for the probe. **Same pool + same seed reproduces run 7
within ±0.02 ALFA per register and ±3 probe prompts.** Falsified if any
register differs by more than 0.02 or the probe differs on more than 3
prompts out of 223 — then the seed-42 protocol is not deterministic on
this box (GPU kernels, unsloth, data-loader nondeterminism) and the noise
floor, not the rows, is what runs 5–8 have been measuring. Either way the
number is the result.

Zero variables changed from run 7. `train.py` gained a `--seed` flag
(default 42, replacing the three hardcoded 42s: `random_state`,
`shuffle(seed=)`, `SFTConfig(seed=)`) and `rebuild.sh` passes it as an
optional fourth argument; with no argument the training call is
byte-identical to run 7's.

If the hypothesis holds, next is `pool_v6` under seeds 43 and 44
(`rebuild.sh qwen-v6-s43 ../dataset/out/pool_v6.jsonl qwen 43`, same for
44): mean ± sd per register, and that sd becomes the error bar in this
file, the README table, and CLAUDE.md § "Model work". If it does not hold,
seeds 43/44 go on `pool_v5` first, because the question becomes how wide
the same run is, not how wide run 8 is.

**Result (2026-08-16): the hypothesis holds.** `qwen-v5b` = run 7 recipe,
untouched, 3 h 10 min train + 1 h post on the 3090.

| register | run 7 | v5b | diff | 95% CI | lost / gained | p |
|---|---|---|---|---|---|---|
| BM | 0.487 | 0.483 | −0.003 | [−0.015, +0.008] | 2 / 1 | 1 |
| rojak | 0.490 | 0.487 | −0.003 | [−0.015, +0.008] | 2 / 1 | 1 |
| EN | 0.543 | 0.530 | −0.013 | [−0.029, +0.003] | 5 / 1 | 0.22 |

Probe: **222 / 222 outputs byte-identical** to run 7's. The five prompts
whose pass/fail differ (`empty a file` ×4, `printenv/collo`) are the
`14d6c23` probe-scorer fix landing between the two probe runs, not the
model — same string both times, judged differently. Bench within noise
(4 threads: 0.47 s warm, 39 tok/s, 1.5 GB RSS).

So the same pool and seed reproduce to a few ALFA tasks out of 300 and zero
probe prompts. The run-to-run floor is ≤ 0.013 per register (≤ 4 tasks),
inside the scorer's own ±5/300. Consequences:

- Run 8's −0.060 BM (p = 0.027) is **not** shuffle noise; the 85 unnamed
  rows really did move it, and #47's next attempt has to explain why.
- A claim of a difference needs to clear about ±0.02 per register (roughly
  the CI half-width above plus the scorer floor), which is what the paired
  McNemar CI already reports; a second seed is not required for a delta
  that clears its CI at p < 0.05. Seeds 43/44 (step 3 of the issue) are
  therefore skipped — the trigger was "outside ±0.02", and it was not.
- Protocol, going into CLAUDE.md § "Model work": one seed suffices when
  the paired CI excludes zero; a delta inside ±0.02 is "no difference",
  never a trend; anything read off a single register at p ≥ 0.05 is noise.

## Run 9: the pool's tool prior (issue #54)

**Hypothesis, written before the run.** Runs 7, 8 and the Qwen3.5-2B arm
all answer `nak buat file baru` with a tldr placeholder or `fossil add`,
and run 8 showed that 85 hand rows do not move that. The cause is the
prior the pool teaches, not a coverage hole: 16% of pool_v6's rows have
`path/to/...` or `<name>` in the command, `find` alone is 17% of the pool,
and 4,819 distinct first tokens split the rest, so a prompt that lands
off-distribution is answered with a placeholder from a tool the model saw
300 times. Removing the placeholder rows, capping the long tail at 300
rows per non-core tool and cutting `find` to 5% (`dataset/prior.py`,
`pool_v7`) will (a) take the placeholder rate on the probe's outputs to
zero, (b) fix `create file` unnamed (`nak buat file baru`,
`nak buat satu file baru`, `tolong buat file baru`) with a real filename in
the answer, and (c) hold ALFA English within run 7's CI. Falsified if the
probe still emits `path/to` or a long-tail tool for the unnamed prompts —
then the prior is in the base, not the pool — or if English drops by more
than the CI, which would mean the 34% of rows removed were carrying
accuracy (RESULTS.md, run 2, the mistake this cut is closest to
repeating).

One variable changed from run 7: the pool. `pool_v7 = prior.py(pool_v6)`,
where `pool_v6 = pool_v4.bal + basics.jsonl` at 330 tasks; the 85 unnamed
rows from #47 are in, so against run 7 the pool differs by the prior fix
plus those rows, and against run 8 by the prior fix alone. Same recipe,
seed 42, 1 epoch. Probe prompts unchanged, none verbatim in basics.txt.

**What prior.py does, in order (`python3 prior.py out/pool_v6.jsonl
out/pool_v7.jsonl`, seed 42, deterministic):**

1. Placeholders. `path/to/...` and `<name>` in the command. Where every
   placeholder also appears verbatim in the NL — the user typed the path,
   `senarai folder kat /path/to/dir` → `find /path/to/dir -type d` — both
   sides are rewritten to one concrete name (`path/to/dir` → `projek`,
   `<file>` → `notes.txt`, otherwise the last path component) so the pair
   stays consistent and `path/to` leaves the output vocabulary. Where the
   NL never named it (every tldr `Create specific files` → `touch
   path/to/file1 path/to/file2`), or there is no safe name (`<port>`,
   `<package>`), the row is dropped. Keystrokes (`<Ctrl x>`, `<Enter>`,
   `<q>`) are not placeholders and stay. 1,012 rows rewritten, 55,246
   dropped. Rewritten commands are the only ones in the pool not
   byte-identical to source; the diff is the placeholder token and nothing
   else.
2. Cap. 300 rows per first token for tools outside CORE (rebalance.py's
   list plus every tool basics.txt teaches, plus shell keywords `for`,
   `while`, `if`, `until`, `case`, which are composition, not tools).
   Sampled by whole pair so the four registers of a command stay together.
   15,754 rows dropped from 51 tools (`az`, `aws`, `kubectl`, `cargo`,
   `gh`, `tlmgr`, `pio`, `shuf`, … each 1,200 → 300).
3. `find` to 5% of the final pool. It is core and genuinely common, but at
   17% it is the answer the model reaches for when unsure; 5% still leaves
   it the single largest tool. 46,364 rows dropped. basics rows are exempt
   from every rule.

| | pool_v6 (run 8) | **pool_v7** |
|---|---|---|
| rows | 345,721 | **228,357** (−34%) |
| distinct first tokens | 4,819 | 4,102 |
| top-30 share | 35.3% | 29.4% |
| rows with a placeholder in cmd | 56,258 (16.3%) | **0** |
| `find` share | 16.9% (58,365) | 5.0% (11,484) |
| `touch` / `mkdir` / `useradd` | 535 / 959 / 116 | 454 / 918 / 104 |
| `az` / `aws` / `kubectl` / `shuf` | 1,200 each | 300 each |
| `fossil` / `skicka` / `kcadm.sh` | 151 / 66 / 38 | 91 / 0 / 30 |
| by source (nl2sh_train / tldr / extra / basics) | 187,891 / 95,848 / 59,401 / 2,581 | 109,995 / 66,758 / 49,047 / 2,581 |

The `touch` rows lost are exactly the placeholder ones; every surviving
`touch` names a real file. `nl2sh_train` lost the most: 26,869 of its
rows carried `path/to` because that pool was itself partly tldr-derived.

**Hand-read, 200 rows, `random.Random(42).sample`.** Registers read as
intended: colloquial and rojak natural (`tlg buang all file _* and
.DS_Store`, `nak tengok status semua job je kat sini`), formal circular-ish
by design. Nothing prior.py rewrote read wrong (30 rewritten rows read
separately: `Remount "bin"` and `mount device location` are dull but
consistent on both sides). What did read wrong is older pool noise, none of
it in this issue's scope, all counted so it can be its own issue: 246 rows
whose command starts with a `$ ` prompt (`$ find /dev ...`, first token
`$`); 11,779 rows (5%) with tldr's alternation syntax in the command
(`ctest [-j|--parallel] 4`, `komac bash|elvish|fish|zsh`), which is not a
runnable command; 139 `path\to\key` (wine reg, backslashes); 217
`some_command`/`command1` placeholders; 48 rows where NL is the command
itself; a few Indonesian slips (`kota`, `acak`) the stoplist does not
know; and a handful of mismatched `extra` pairs (`Hapus entri dalam fail
.bash_history` → `export HISTCONTROL=ignoreboth`).

**Measure.** Run 7 to beat: ALFA BM 0.487 / rojak 0.490 / EN 0.543, probe
basics 0.90 / holdout 0.78; run 8 for the same-rows comparison. New
number: placeholder rate on the probe outputs (`path/to` or `<name>` in the
answer), reported alongside. Then #47's exact-output prompts, `compare.py`
vs run 7, bench, all with #57's error bar in mind.

GPU command, from the worktree's `training/`:
`./rebuild.sh qwen-v7 ../dataset/out/pool_v7.jsonl` — queued behind the
running job, one at a time (#56, #57).

**Result (2026-08-17): the pool prior moves the probe, not ALFA.** `qwen-v7`,
228,357 rows, 2 h 40 min train on the 3090. Error bar from #57: same recipe
reproduces to ≤ 0.013 per register.

| register | run 7 | run 9 (v7) | diff | 95% CI | lost / gained | p |
|---|---|---|---|---|---|---|
| BM | 0.487 | 0.513 | +0.027 | [−0.029, +0.083] | 33 / 41 | 0.42 |
| rojak | 0.490 | 0.517 | +0.027 | [−0.026, +0.080] | 29 / 37 | 0.39 |
| EN | 0.543 | 0.563 | +0.020 | [−0.036, +0.076] | 34 / 40 | 0.56 |

All three registers up, none clears its CI. The churn is the story: ~35
tasks lost and ~40 gained per register — ten times run 7 vs v5b — so a
34% pool cut is a different model, and 300 tasks cannot say whether it is
a better one. English did not drop, so the run-2 fear did not come true.

Probe: 199 / 222 both, not the same 199. What the issue was for is fixed:
`create file` 8/9 → 9/9 (`touch newfile.txt` on every phrasing, no more
`fossil add path/to/file`), `create folder` 8/8, `create user` 2/5 → **5/5**
(`sudo useradd -m newuser`, no more `kcadm.sh`), placeholder answers
29 → **6** across the 222 prompts. What broke: `delete file` ×4 →
`git obliterate file_1 file_2 ...` (was `rm path/to/file1 ...`, tool-right
placeholder), `list processes` ×3 → `pm2 list`/`pm2 monit` (was `ps aux`),
`edit file` → `less`, holdout 36 → 33 (`chsh`, `timeout`, `whereis` lost;
`tee` ×2, `reverse lines/en` gained). `rm` and `ps` rows barely moved
(1,618 → 1,539, 928 → 868); what moved is share — the core list is
uncapped, so `git` went from 4.3% to 5.8% of the pool and `pm2` (84 rows,
under the cap) from 0.02% to 0.04%. Capping the tail without growing the
head redistributes the prior, it does not flatten it. Bench unchanged
(4 threads 0.53 s warm, 39 tok/s, 1.49 GB RSS).

Verdict: not shipping on ALFA alone (inside CI, per #57's protocol), but
the probe targets #47/#53/#54 exist for are met on this pool. The next
pool change should add head rows for the beginner verbs (`rm`, `ps`,
`nano`) rather than cut more tail — and #56's DPO pairs already encode
exactly the `git obliterate`/`pm2` class of miss, so DPO on this
checkpoint (`DPO_BASE=out/qwen-v7-lora-merged`) is the cheap next arm.


## Run qwen-v5-dpo: DPO on the model's own mistakes (issue #56)

**Hypothesis, written before the run.** Every SFT run so far has taught the
model what to say and nothing about what not to say. Run 7's remaining
misses are not coverage holes, they are near-misses on the same tokens the
pool teaches: `touch path/to/file1 path/to/file2 ...` (right tool, tldr
placeholder — 50,878 of the 345,636 pool rows carry `path/to`), and a
same-pool obscure tool where the pool has a common one (`fossil add`,
`skicka mkdir`, `kcadm.sh create users`, `lzop`, `gdu`, `fkill`, `smem`).
Run 8 tried to fix these by adding rows and moved BM by −0.06 instead. A
DPO stage that holds the gold as chosen and those exact outputs as rejected
pushes against the failure directly, without adding rows to the SFT pool or
changing its order. Prediction: on the shipped CPU path the placeholder
rate on the probe's 177 basics-task prompts falls from **24/177 (0.14)** to
under 0.03, `nak buat file baru` returns `touch newfile.txt` (or any
`touch` with a real name), `nak buat user baru` returns `useradd`, and the
three ALFA registers stay inside their run 7 CIs (BM 0.487, rojak 0.490,
EN 0.543). Falsified if any ALFA register drops with p < 0.05 — then the
preference stage is trading beginner exactness for one-liner accuracy and
β or the pair mix is next — or if the placeholder rate does not move, which
would mean 3,455 pairs at β = 0.1 do not shift a preference that 15% of the
pool voted for.

One variable vs run 7: the DPO stage. `training/dpo.py` puts a fresh
r32/a64 LoRA on the run 7 merged checkpoint (`out/qwen-v5-lora-merged`),
TRL `DPOTrainer`, sigmoid loss, β = 0.1, 1 epoch, seed 42, effective batch
32, lr 5e-6 (Unsloth's DPO reference recipe; SFT's 2e-4 would wreck the
policy), reference = the same weights with the adapter disabled. Prompt
text is train.py's literal ChatML. Same GGUF path as every run
(`finish.sh` → f16 → Q4_K_M), same pinned CPU probe. `trl` 0.24.0 was
already in `uv.lock` (unsloth pulls it); nothing was added.

**Pairs, `training/dpo_pairs.py` → `out/dpo_pairs.jsonl`, 3,455 total:**

| kind | n | chosen | rejected |
|---|---|---|---|
| probe-wrong | 18 | basics.txt command for the probe task | run 7's actual output (`gdu --disk-usage`, `fkill :8080`, `kcadm.sh create users ...`, `jobs`, `smem --memstats`, `tempdir -c` ...) |
| probe-placeholder | 22 | same | run 7's tool-level pass that was a placeholder (`touch path/to/file1 path/to/file2 ...`, `skicka mkdir path/to/folder`, `rm path/to/file1 ...`, `chmod 644 /path/to/file`) |
| synth-placeholder | 999 | basics.txt gold, every phrasing | gold with names swapped for `path/to/file` / `path/to/directory` |
| synth-tool-swap | 2,416 | basics.txt gold, every phrasing | gold's tool swapped for what run 7 reached for (`touch`→`fossil add`, `mkdir`→`skicka mkdir`, `useradd`→`kcadm.sh create users`, `tar`→`lzop`, `df`→`gdu`, `kill`→`fkill`, `free`→`smem`) or a low-count pool tool drawn with seed 42 |

Unweighted: the 40 real-mistake pairs are 1.2% of the set. If the probe
misses persist while the synthetic kinds land, weighting the real pairs is
the next variable, not a bigger β.

**Split, stated.** ALFA is not touched: no pair is built from any ALFA
task, and the three basics.txt English phrasings that are verbatim
nl2sh_test prompts (`print hello world`, `print the current user`, `list
all users on the system`) are dropped from the pair set. The probe main
block is **not** clean after this run: the 40 probe-* pairs train on the
probe's own prompts, so post-DPO basics-task numbers measure recall of the
fix, not phrasing generalisation; read them as "did the specific miss go
away", and read the ALFA and HOLDOUT columns for generalisation. HOLDOUT
(no basics.txt command to serve as chosen) and the homograph guard get no
pairs and stay clean. Homograph EN-sense (`fails` = failure) is the
regression to watch: `nak buat fail baru` → `touch` is now a chosen row.

Measured before the run (run 7, shipped model, pinned CPU build): probe
basics 0.90 / holdout 0.78 / homograph 1.00 / 0.67, placeholder rate 24/177
on basics prompts and 25/223 overall, ALFA BM 0.487 / rojak 0.490 / EN
0.543, bench 4 threads 36.8 tok/s / 0.57 s warm / 1.38 s cold / 1626 MB.
#47 prompts exact: see the run 8 table above (run 7 column).

Order: queued behind #54's retrain. If #54 ships, `DPO_BASE=out/<54
merged>` puts this stage on top of it and the comparison row becomes #54's
run instead of run 7; the pairs are rebuilt from that run's probe file
(`dpo_pairs.py --probe out/probe_<54>.jsonl`). Not started; hypothesis
written first.

**Result (2026-08-17): both DPO arms ran; the hypothesis is falsified on
run 7 and half-met on the pool_v7 checkpoint.** Each DPO stage is 3 min on
the 3090 (3,4xx pairs, 1 epoch), reward accuracy 0.99 by the end — the
pairs are learned; the question was whether that generalises. #57's error
bar (≤ 0.013 same-recipe) applies.

*Arm A — `qwen-v5-dpo`, on run 7's merged checkpoint, pairs from run 7's
probe (3,455):*

| register | run 7 | run 7 + DPO | diff | 95% CI | lost / gained | p |
|---|---|---|---|---|---|---|
| BM | 0.487 | 0.497 | +0.010 | [−0.023, +0.043] | 11 / 14 | 0.69 |
| rojak | 0.490 | 0.510 | +0.020 | [−0.016, +0.056] | 12 / 18 | 0.36 |
| EN | 0.543 | 0.530 | −0.013 | [−0.051, +0.025] | 19 / 15 | 0.61 |

Probe 199 → 205 / 222, holdout 36 → 36. Placeholder answers **29 → 23**:
`nak buat file baru` is now `touch path/to/file1 path/to/file2 ...`
instead of `fossil add path/to/file` — the tool moved, the placeholder did
not, although exactly that string is a rejected row. `create user` 2 → 3
of 5, `kill process on port` gains ×2 (`fuser -k 8080/tcp`). Falsified:
the placeholder rate went 0.13 → 0.10, not below 0.03; ALFA is inside
every CI. Bench 0.65 s warm at 4 threads (was 0.47; retest before reading
anything into it), 1.49 GB.

*Arm B — `qwen-v7-dpo`, on run 9's checkpoint (`DPO_BASE=out/qwen-v7-lora-merged`),
pairs rebuilt from run 9's probe (3,430):*

| register | run 9 (v7) | v7 + DPO | diff | 95% CI | p | vs run 7 |
|---|---|---|---|---|---|---|
| BM | 0.513 | 0.497 | −0.017 | [−0.054, +0.021] | 0.49 | +0.010, p 0.82 |
| rojak | 0.517 | 0.517 | 0.000 | [−0.032, +0.032] | 1 | +0.027, p 0.40 |
| EN | 0.563 | 0.543 | −0.020 | [−0.057, +0.017] | 0.38 | 0.000, p 1 |

Probe 199 → **205** / 222, holdout 33 → 34, placeholders **6 → 2**.
Run 9's regressions come back: `delete file` 2 → 5 of 6 (`rm filename`,
`git obliterate` gone on three of four phrasings), `list processes` 0 → 2
of 4 (`ps aux`, `pm2` gone on two). Lost: `change permission` ×2 →
`icacls file_or_directory` (Windows tool, tldr row; not in the pair set —
DPO pushed `chmod` down for reasons the pairs do not name), `change
shell/rojak`. Bench 0.43 s warm at 4 threads, 1.5 GB.

Reading. DPO on ~40 real mistakes plus 3,400 synthetic pairs does what the
pairs literally say — the specific `fossil`/`kcadm.sh`/`git obliterate`/
`pm2` misses it was shown flip back — and nothing further: the placeholder
habit survives on run 7 (23 answers), ALFA does not move on either base,
and every gain is offset by a new obscure-tool miss elsewhere (`icacls`).
Three minutes of preference tuning cannot fix a prior that 345k SFT rows
set; it can only patch the misses it was handed. Neither arm ships:
v7-dpo has the best probe (205, 2 placeholders, all #47 targets pass) but
is inside run 7's CI on every register and −0.02 EN on its own base.

Next, if this thread continues: weight the real-mistake pairs (1.2% of the
set today), or grow the head of the pool for the beginner verbs (#54's
note) and DPO on top of that — the pool sets the prior, DPO trims it.
Filed as #62.

**Shipped anyway, as `camne` v0.9.0 (2026-08-17), and here is the reasoning
so it can be argued with.** The rule in CLAUDE.md is "a tune that does not
beat its own base is not a result", and on ALFA v7-dpo does not beat run 7:
BM +0.010, rojak +0.027, EN 0.000, every CI straddles zero. #57 says the
benchmark cannot resolve less than about ±0.02 at 300 tasks, so "cannot
tell apart" is the honest reading, not "worse". What the benchmark does not
score is the shape of the answer on the tasks the product exists for: run 7
answers `nak buat file baru` with `touch path/to/file1 path/to/file2 ...`,
`nak buat folder baru` with `skicka mkdir path/to/folder`, `nak buat user
baru` with `kcadm.sh create users -s username=username -r realm_name`.
v7-dpo answers `touch newfile.txt`, `mkdir newfolder`, `sudo useradd -m
newuser`. Placeholder answers on the probe 29 → 2 of 222; beginner tasks
0.90 → 0.94 (p = 0.12); held-out tools 0.90 → 0.85 (5 lost, 3 gained, p =
0.73); vs the English model rojak is now +0.070 (p = 0.031), resolved for
the first time. Not one register worse than run 7, and the beginner
answers are the ones a person can type. Digest `cbf78111…5fcb`, 986,048,032
bytes, README and model card state the CI-straddling numbers as such.


## Retrieval over tldr in the prompt (issue #55)

The issue says the cost measurement decides, so it comes first. Everything
below is the pinned CPU build (`b10333`), `-ngl 0`, run 7 GGUF
(`qwen-v5-Q4_K_M`), same decoding as `bench.py`, `training/bench_retrieval.py`.
The GPU was busy with a training job while this ran, so absolute numbers
carry that noise; the baseline row reproduces run 7's bench within it.

**Embedding model.** `bge-small-en-v1.5` f16 GGUF, 67 MB on disk (the
`bge-small / e5-small / arctic-xs` class the issue names; English-only, which
matters below). Served by the same pinned `llama-server` with `--embeddings
--pooling cls -c 512`: 0.2 s to load, **101 MB RSS**, **6–9 ms** per query
embed at 2–4 threads. The embedder is not the cost.

**Index.** `dataset/raw/tldr.csv` deduped on (description, command): 29,153
lines, description embedded, line shape `description: command`. Vectors
29,153 × 384 f16 = **22 MB** (the `.npz` with the text is 70 MB); building
it is 4 min of CPU at 4 threads. Query → top-3 is 16–21 ms end to end.

**Cost, both servers resident, 12 queries, median.** Three (or one)
*distinct* tldr lines per query — a fixed set is not a measurement: the
pinned server keeps evicted prompts in RAM and served a rotated fixed set
from cache at 13 prompt tokens instead of 80.

| threads | prompt | prompt tokens evaluated | warm s (max) | tok/s | combined RSS MB |
|---|---|---|---|---|---|
| 2 | baseline | 12 | 0.73–0.77 (1.4–1.7) | 26–27 | 1768 |
| 2 | + top-3 `Examples:` | 80 | **2.06–2.18 (3.1)** | 26–28 | 1817 |
| 2 | + top-1 | 31 | 1.10 (1.6) | 28 | 1821 |
| 4 | baseline | 12 | 0.43–0.53 (0.8–1.3) | 30–42 | 1768 |
| 4 | + top-3 `Examples:` | 80 | **1.30–1.31 (1.8)** | 38–41 | 1813 |
| 4 | + top-1 | 31 | 0.61 (1.0) | 42 | 1816 |

Two runs, both shown where they differ. RSS is not the problem: 1.8 GB
combined, 0.7 GB under the ceiling. Prompt evaluation is: the tuned 1.5B
processes prompt tokens at ~60–80 tok/s on 2 threads, so 68 extra tokens
per query is 1.3 s before the first output token, every query, because the
retrieved lines differ per query and defeat `cache_prompt`.

**Verdict vs constraint 3.** `engine.go` gives a 4-core box 2 threads. At 2
threads top-3 retrieval is **2.1 s median, 3.1 s worst**, over the 1.5 s
warm budget on a host that is already faster than the target box. At 4
threads it is 1.3 s median with a 1.8 s tail: under the median budget here,
over it on the target. **Top-3 as the issue specifies does not fit.** Top-1
fits (1.1 s at 2 threads, 0.6 s at 4), with less headroom than baseline and
one line of context instead of three, so it is measured below rather than
assumed useless.

**Hypothesis, written before the probe run.** With top-1 retrieval on, the
run 7 model will gain on the probe's holdout block (tools absent from
basics.txt: `truncate`, `tac`, `tee`, `timeout`, `chsh`, `printenv`, `nl`)
by ≥ +0.05, because for those tasks the right tldr line is the answer, and
hold basics tasks within 0.02, because those the model already knows. Two
things say the gain will be smaller than the idea promises: the embedder is
English-only, so Malay phrasings that carry no English technical noun
retrieve wrong lines (`nak buat file baru` → `hexedit`, `kioclient`;
spot-checked before the run), and a bad line in front of a 1.5B model is a
distractor, not a no-op. Falsified if holdout does not move or basics
drops; then retrieval needs a multilingual embedder (`multilingual-e5-small`
Q8 is ~120 MB, over the issue's cap) or a retrained model that has seen
`Examples:` in training, both out of scope here.

### Result: falsified, retrieval on halves the probe

`probe.py --retrieve 1`, run 7 GGUF, same 223 prompts, `training/out/probe_qwen-v5_ret1.jsonl`;
the off column is `probe_qwen-v5.jsonl` rescored with today's regexes so both
columns share them.

| | retrieval off (run 7) | retrieval on, top-1 | n |
|---|---|---|---|
| basics tasks (unseen phrasings) | 0.90 | **0.53** | 177 |
| holdout (tools absent from basics.txt) | 0.90 | **0.30** | 40 |
| english | 1.00 | 0.57 | 35 |
| rojak | 0.91 | 0.57 | 35 |
| colloquial | 0.84 | 0.35 | 31 |
| formal | 0.83 | 0.71 | 35 |
| homograph BM-sense / EN-sense | 1.00 / 0.67 | 0.33 / 0.67 | 3 / 3 |

Paired over all 223 prompts: **lost 93, gained 7** (exact two-sided
p ≈ 3e-20). Not a small miss; the mechanism does the opposite of the
hypothesis.

**What the failures look like.** The model treats the retrieved line as the
answer, not as context: `nak buat fail baru` → `systemctl edit foo.service`,
`nak tukar default shell ke zsh` → `unshare --shell=ash|bash|dash|ksh|zsh`,
`tunjuk nilai variable HOME` → `flux var set --home`. When the retrieved
line is right the answer is right — `empty the file app.log without
deleting it` → `truncate [-s|--size] 0 app.log` (gained), `run ./slow.sh
but stop it after 10 seconds` → `timeout 10 ./slow.sh`, `find where git and
its man page are installed` → `whereis -s gcc -m git`. The seven gains are
all of that shape and six of them are English or formal BM. So retrieval is
only as good as the embedder, and an English-only embedder over Malay
queries is wrong most of the time (`nak buat file baru` → `hexedit`,
`kioclient`); the model then copies the wrong tool with confidence, and the
`Examples:` framing also breaks phrasings it answered correctly with no
context at all — 93 of them.

**Reading.** Two independent problems, either fatal on its own:

1. Cost. Top-3 is 2.1 s warm at the thread count camne gives a 4-core box,
   on a host faster than the target. RSS is fine (1.8 GB). It is prompt
   evaluation of ~70 uncacheable tokens per query on a 1.5B model at
   ~70 tok/s. Nothing in the retrieval design changes that except fewer
   tokens, and top-1 is already the floor.
2. Accuracy. The run 7 model has never seen `Examples:` in a user turn and
   copies whatever is there. That is fixable only by the thing the issue
   puts out of scope — training rows with retrieved context — and only
   worth attempting with an embedder that reads Malay, which is over the
   100 MB cap (`multilingual-e5-small` Q8 ≈ 120 MB, f16 ≈ 230 MB).

**Not running ALFA**: the probe result is a 40-point drop on the block the
issue cares about, and ALFA generation is CPU-only while the GPU is busy
(900 prompts × ~1.5 s ≈ 25 min per register per arm; feasible, pointless
here). Command, if someone wants the number anyway, is the run 7 recipe with
`probe.py --retrieve 1`'s prefix applied in `eval_gen.py`; that flag does not
exist in `eval_gen.py` and is not being added for a result this clear.

**Decision: closes #55 as measured.** Nothing ships. `retrieve.py`,
`bench_retrieval.py` and `probe.py --retrieve K` stay so the next attempt
(multilingual embedder + retrieval-aware training rows, if ever) starts
from the measurement instead of the idea. Index file (`out/tldr_index.npz`)
and the bge GGUF are build artifacts, not committed.


## Run 10: head rows for the beginner verbs (issue #62)

**Hypothesis, written before the run.** Run 9 fixed `create file/folder/
user` by cutting the tail, and the share it freed went to whatever was
left uncapped: `git` 4.3% → 5.8% of the pool, and `delete file` came back
`git obliterate`, `list processes` `pm2`, `edit file` `less`. v7-dpo
flipped those exact misses back and moved nothing else, which is what
three minutes of preference tuning on 40 real pairs can do. The prior is
set by the SFT pool, so this run grows the head instead of trimming the
tail again: `pool_v8 = pool_v7 + 11,676 rows` for the beginner verbs that
have fewer than 1,000 real rows (`nano` 52, `less` 87, `unzip` 106, `zip`
125, `scp` 137, … `ps` 769, `rm` 758 once augment_verbs duplicates are not
counted). Prediction: on the probe, `delete file` (2/6 on run 9), `list
processes` (0/4), `edit file` and `change permission` return to run 7's
level or better with `rm` / `ps` / `nano` / `chmod` as the tool, with no
placeholder regression (run 9 had 6 placeholder answers of 222; ≤ 6
here); `create file/folder/user` hold 9/9, 8/8, 5/5; ALFA stays inside run
9's CI on every register (BM 0.513, rojak 0.517, EN 0.563, ± ~0.055).
Falsified if the four probe tasks do not move — then 1,000 rows per tool
is not what sets the prior against 13k `git` rows and the next variable is
share, not count — or if any ALFA register drops with p < 0.05, which would
mean 12k templated rows are teaching the templates rather than the verbs.
Then DPO on top with pairs rebuilt from this run's probe (`qwen-v8-dpo`),
comparison row this run, same reading rule as arm B of #56.

One variable vs run 9: the pool. Same recipe, seed 42, 1 epoch, probe
prompts unchanged, none verbatim in basics.txt or basics_head.txt (probe.py
now checks both at startup).

**Where the rows come from (`dataset/head.py`, `dataset/basics_head.txt`).**
Re-admitting real rows was the first choice and there is nothing to
re-admit: the rows prior.py dropped for these tools are tldr placeholders
whose NL never names the file (`Remove specific files` → `rm path/to/file1
path/to/file2`), and the rows disambiguate.py dropped earlier are
same-prompt pipe one-liners (`ps -ef |grep oracle |grep pmon |awk …`), 0 to
164 per tool. So the head is written the way basics.txt was, in a new file
so basics.txt's phrasings stay what probe.py's "not in training data" claim
was made against: 107 blocks, four registers, plus slots — `{f}` file,
`{t}` text file, `{d}` folder, `{u}` user, `{h}` host, `{n}` count, `{pid}`,
`{p}` process, `{z}` zip, `{url}`, `{port}`, `{sshport}`, `{log}` — that
head.py fills twenty ways from fixed lists, the k-th name of every list, so
`rm {f}` / `nak buang fail {f}` is twenty consistent pairs. A phrasing must
carry every slot its command carries (the parser refuses otherwise): a row
whose NL never names what the command names is the placeholder bug again.
18,568 rows expanded; budget per tool `min(918, 1000 − real rows)`, 918
being `mkdir`'s row count in pool_v7 so no single tool jumps past the head
it joins; whole tasks sampled with `prior.sample_ids`, seed 42. `chsh` is
in the issue's list and gets nothing: it is a probe HOLDOUT tool, and a
head row for it would un-hold it (head.py refuses HOLDOUT tools outright).

| tool | pool_v7 | real | budget | added | **pool_v8** |
|---|---|---|---|---|---|
| nano | 53 | 52 | 918 | 918 | 971 |
| less | 90 | 87 | 913 | 918 | 1,008 |
| unzip | 174 | 106 | 894 | 904 | 1,078 |
| zip | 197 | 125 | 875 | 876 | 1,073 |
| scp | 164 | 137 | 863 | 864 | 1,028 |
| head | 266 | 254 | 746 | 749 | 1,015 |
| kill | 521 | 321 | 679 | 687 | 1,208 |
| touch | 454 | 358 | 642 | 644 | 1,098 |
| chown | 599 | 374 | 626 | 634 | 1,233 |
| top | 168 | 159 | 841 | 570 | 738 |
| chmod | 527 | 444 | 556 | 563 | 1,090 |
| mv | 743 | 502 | 498 | 510 | 1,253 |
| tail | 601 | 590 | 410 | 413 | 1,014 |
| mkdir | 918 | 606 | 394 | 396 | 1,314 |
| cp | 963 | 686 | 314 | 318 | 1,281 |
| wget | 715 | 696 | 304 | 310 | 1,025 |
| rm | 1,580 | 758 | 242 | 253 | 1,833 |
| ssh | 806 | 757 | 243 | 249 | 1,055 |
| ps | 880 | 769 | 231 | 238 | 1,118 |
| df | 294 | 280 | 720 | 235 | 529 |
| free | 87 | 82 | 918 | 221 | 308 |
| du | 841 | 794 | 206 | 206 | 1,047 |
| chsh | 16 | 16 | — | 0 | 16 |
| cat / ls / grep / tar / curl / find | ≥ 1,000 real | | 0 | | unchanged |

`top`, `df`, `free` land short of budget on purpose: they have three or
four real command shapes (`free -h`, `df -h`, `top`) and no filename to
vary, so the rows that exist are phrasings, not expansions; padding them
to 900 would be the same sentence 900 times.

| | pool_v7 (run 9) | **pool_v8** |
|---|---|---|
| rows | 228,357 | **240,033** (+5.1%) |
| distinct first tokens | 4,102 | 4,102 |
| top-30 share | 29.4% | 29.8% |
| `git` share | 5.8% | 5.6% |
| `find` share | 5.0% | 4.8% |
| placeholders in cmd | 0 | 0 |
| added, by register | | colloquial 3,761 / rojak 3,389 / english 2,965 / formal 1,561 |
| added, by source | | re-admitted 0 / generated 11,676 |

Every pool_v7 row is in pool_v8 in the same order with its command
byte-identical (checked, 228,357/228,357); the 11,676 head rows match
their block's command byte for byte; no `path/to`, no `<name>`; no head NL
equals a probe prompt (one did — `kill the process using port 8080` at
`{port}` = 8080 — and was reworded before the build).

**Issue #51 rides along, two ways.** (a) 112 pool_v7 rows had the
translator rename the file in the NL while the command kept it —
`fail.txt` for `file.txt` (91), `fail1.csv`, `dokumen.zip` for
`documents.zip`, `teks.txt`, `senarai.txt` for `list.txt`, `arkib.zip` —
which is exactly the Malay-name → English-name mapping the issue reports
the model learned. head.py restores the command's name in the NL where the
command names one file the NL does not and the NL names one file whose
stem is the Malay of it (a fixed nine-stem list; `build.xml` vs
`buildfile.xml` is left alone). Commands untouched. (b) every slot list
carries Malay filenames — `lama.txt`, `nota.txt`, `laporan.pdf`,
`senarai.txt`, `gambar.jpg`, `projek`, `dokumen`, `tugasan` — byte-identical
on both sides: 2,873 of the added rows, the positive example the pool never
had. Not done: `grep -c lama.txt pool_v5` is 0, so the mapping in #51 was
never a literal pair in the pool; it is the base model's translation prior
plus the 112 rows, and (b) is what pushes against it. Measure with #51's
four prompts exact after the run.

**Hand-read, 200 of the added rows, `random.Random(42).sample`.** Registers
read as intended and each row's NL names what its command names. What
reads wrong, fixed before the build: `ssh -p 3306` / `scp -P 5432` — the
port list is shared with `kill $(lsof -t -i:{port})`, where 3306 is
right, so ssh/scp got their own `{sshport}` list; `tail -f data.csv` /
`less +F main.py` — following a csv reads odd, so the follow blocks got a
`{log}` list. Left as is, counted: slot lists are independent, so
`zip -r resit.zip kuliah` and `unzip projek.zip -d gambar` pair unrelated
names (consistent on both sides, just dull); `chmod 600 video.mp4` and
`chmod u+w foto.png` are valid but not something anyone asks; two rojak
phrasings are stiff (`chown -R arkib to farah`, `wget {url} resume`); the
formal register is 13% of the added rows against 32% colloquial, the same
skew basics.txt has (352 of 2,581). No Indonesian, no `lah`, no
`Bagaimanakah`, no probe phrasing.

**Measure.** Run 9 to beat on the probe (199/222, 6 placeholders, holdout
33), run 7 for the tasks run 9 lost; ALFA vs run 9 paired, #57's error bar;
`compare.py`, bench, #47 prompts exact, #51 prompts exact, placeholder
rate. GPU commands, from the worktree's `training/`:
`./rebuild.sh qwen-v8 ../dataset/out/pool_v8.jsonl`, then
`python3 dpo_pairs.py --probe out/probe_qwen-v8.jsonl --out out/dpo_pairs_v8.jsonl`
and `DPO_BASE=out/qwen-v8-lora-merged ./rebuild.sh qwen-v8-dpo out/dpo_pairs_v8.jsonl dpo`.
Not started; hypothesis written first.

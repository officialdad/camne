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

# Bake-off results

InterCode-ALFA, unmodified scorer, 300 tasks per set. Fixed settings, stated
with every number: temperature 0, `n_predict` 64, embed threshold 0.75,
`repeat_penalty` 1.08 / `repeat_last_n` 64, GBNF single-line grammar — the
same settings `internal/engine` sends. Seed 42. BM set is the colloquial
translation in `dataset/eval_bm_300.jsonl`; EN set is the untouched
NL2SH-ALFA test split, kept as the regression control.

| model | training pool | BM pass | EN pass | size |
|---|---|---|---|---|
| nl2sh-1.5b (shipping today) | whatisit's English pool | 0.297 | 0.593 | 986 MB |
| camne-qwen (run 1) | NL2SH-ALFA + tldr, 4 registers, 247k rows | **0.387** | 0.493 | 986 MB |

Paired exact McNemar against the untuned base:

- BM: +0.090 (89 -> 116 of 300), 34 lost / 61 gained, **p = 0.0073**
- EN: -0.100 (178 -> 148 of 300), 60 lost / 30 gained, **p = 0.0021**

## Run 1 verdict: not shippable

The tune bought Malay by selling English, both significantly. The English
control set exists to catch exactly this, and it did.

The regressions are tool substitutions, not degeneration:

| prompt | base | run 1 |
|---|---|---|
| print the system uptime | `uptime` | `rfetch -t` |
| print the system memory usage | `free -m` | `smem --system` |
| print environment variables | `env` | `go env` |

Cause is distribution flattening, not bad rows. NL2SH-ALFA is
benchmark-shaped: 40,938 pairs over 3,966 tools, weighted toward the common
ones. tldr is a reference: one page per tool, ~6 examples each, spread evenly
over 4,691 tools. Mixing them at 58/42 gives `smem` the same weight as
`free`, so the model stops preferring the obvious answer. Filtering tldr by
tool overlap cannot fix it — 3,563 of its 4,691 tools also appear in
NL2SH-ALFA. The mix is the variable, not the membership.

Run 2 (in progress) drops tldr entirely: same recipe, same seed, 159,052
rows, one variable changed. If English recovers while Malay holds, that is
the shippable model and tldr returns later as a weighted minority.

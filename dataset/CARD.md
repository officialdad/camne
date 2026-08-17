---
license: apache-2.0
language:
  - ms
  - en
task_categories:
  - text-generation
tags:
  - bash
  - shell
  - nl2sh
  - bahasa-melayu
size_categories:
  - 100K<n<1M
pretty_name: camne four-register pool
---

# camne-pool

Natural-language request in, one shell command out, with the request in four
registers: formal Bahasa Melayu, colloquial Malay, rojak (Malay-English
mix), English. This is the training pool behind
[camne](https://github.com/officialdad/camne) and the shipped model
[opariffazman/camne-1.5b-Q4_K_M](https://huggingface.co/opariffazman/camne-1.5b-Q4_K_M).
Numbers for every run are in the repo's
[RESULTS.md](https://github.com/officialdad/camne/blob/main/RESULTS.md).

## Files

| file | rows | what |
|---|---|---|
| `pool_v7.jsonl` | 228,357 | the pool camne v0.9.0 was trained on |
| `basics.jsonl` | 2,581 | hand-written beginner tasks, already inside pool_v7 |
| `eval_bm_300.jsonl` | 300 | InterCode-ALFA test prompts, colloquial Malay |
| `eval_rojak_300.jsonl` | 300 | InterCode-ALFA test prompts, rojak |

The two eval files are for measurement only. Do not train on them. They
carry the ALFA gold command in `cmd` (the same gold the public ALFA scorer
uses), so a model that has seen them is not measurable with ALFA anymore.

## Row schema

```json
{"id": "nl2sh_train:21667", "register": "colloquial", "nl": "nak tengok file kat sini yang lebih besar dari 10KB je", "cmd": "find . -size +10k"}
```

`register` is one of `formal`, `colloquial`, `rojak`, `english`. The `id`
prefix names the source (see NOTICE). One example row per register, taken
from the pool as-is:

```json
{"id": "nl2sh_train:7", "register": "formal",     "nl": "Mengetahui pengguna yang sedang log masuk ke dalam sistem", "cmd": "who"}
{"id": "nl2sh_train:7", "register": "colloquial", "nl": "nak tengok user login kat sini?",                             "cmd": "who"}
{"id": "nl2sh_train:7", "register": "rojak",      "nl": "check siapa dah login je",                                    "cmd": "who"}
{"id": "nl2sh_train:7", "register": "english",    "nl": "who is currently logged into the system",                     "cmd": "who"}
```

## Commands are never translated

`cmd` is byte-identical to the source dataset for 225,143 of 228,357 rows.
The rest are 2,581 hand-written rows (no upstream source) and 633 rows
where a `path/to/...` placeholder was replaced by a concrete name on both
sides of the pair (`prior.py`, issue #54); the placeholder token is the only
diff. Technical nouns (file, folder, delete, download, server, ...) are kept
English in the Malay text on purpose: that is how Malaysians type them.

## How the pool is built

Stdlib-only Python, in `dataset/` of the repo:

1. `fetch.py`, `tldr.py`, `extra_sources.py`: pull the sources into `raw/*.csv`.
2. `registers.py`: for each English pair, a local Gemma-SEA-LION-v3-9B-IT
   endpoint writes the formal, colloquial and rojak versions of the request.
   No external API; nothing leaves the machine.
3. `stoplist.py`: force technical nouns back to English, strip particles.
   `verify.py` asserts every command byte-identical to its source.
4. `disambiguate.py`, `augment_verbs.py`, `rebalance.py`: name the tool where
   one prompt maps to many commands, fill in Malay verbs the translator never
   used, fix the tool-frequency inversion.
5. `basics.py`: `basics.txt` (hand-written beginner tasks) to `basics.jsonl`.
6. `prior.py`: drop or rewrite placeholder rows, cap the long tail at 300
   rows per tool, cut `find` to 5%. Output is `pool_v7.jsonl`.

## Sources and licence

Apache-2.0 for the pool as a whole; each source keeps its own licence. By
measured share of pool_v7: NL2SH-ALFA 48.2% (MIT), tldr-pages 29.2%
(CC-BY-4.0), cli-commands-explained 18.5% (CC0-1.0), git-instruction-dataset
3.0% (MIT), hand-written 1.1% (Apache-2.0). The Malay text is the output of
Gemma-SEA-LION-v3-9B-IT (Gemma Terms of Use govern the model, not its
outputs). Full table, links and the CC-BY attribution: [NOTICE](NOTICE).

# dataset pipeline — milestone 5

English NL→command pairs in, four-register BM rows out. Commands are never
touched: byte-identity is checked, not assumed.

Stdlib-only Python 3 (mirrors the repo's no-dependency rule). No venv needed.

## Flow

```
fetch.py      # source pools → raw/           (NL2SH-ALFA public; whatisit pool needs HF_TOKEN + access)
registers.py  # raw CSV → out/rows.jsonl      (drives a local LLM endpoint, resumable)
stoplist.py   # out/rows.jsonl → out/rows.clean.jsonl  (force technical nouns back to English, marker stats)
verify.py     # asserts every command byte-identical to source; nonzero exit on drift

# after all three pools are cleaned and concatenated into out/pool_v3.jsonl:
disambiguate.py   # → out/pool_v3.train.jsonl  name the tool in prompts that
                  # map to many commands, drop same-prompt-same-tool dupes
augment_verbs.py  # → out/pool_v3.aug.jsonl    fill in Malay verbs the
                  # translator never reached for (`cipta` had 2 rows)
rebalance.py      # → out/pool_v3.bal.jsonl    fix the tool-frequency
                  # inversion (`shuf` outweighed `touch` 11 to 1)
basics.py         # basics.txt → out/basics.jsonl  hand-written beginner rows
prior.py          # pool_v6 (= pool_v4.bal + basics) → out/pool_v7.jsonl
                  # drop/rewrite path/to placeholders, cap the long tail at
                  # 300, find to 5% (issue #54)
```

Full rebuild from raw, no GPU:

```sh
for f in rows tldr_rows extra_rows; do python3 stoplist.py out/$f.jsonl out/$f.clean.jsonl; done
cat out/rows.clean.jsonl out/tldr_rows.clean.jsonl out/extra_rows.clean.jsonl > out/pool_v3.jsonl
python3 verify.py raw/nl2sh_train.csv out/rows.clean.jsonl
python3 disambiguate.py  out/pool_v3.jsonl     out/pool_v3.train.jsonl
python3 augment_verbs.py out/pool_v3.train.jsonl out/pool_v3.aug.jsonl --floor 2500
python3 rebalance.py     out/pool_v3.aug.jsonl   out/pool_v3.bal.jsonl
python3 test_stoplist.py
```

## Registers are not interchangeable

`stoplist.py` runs two separate jobs and they must not be merged again.
Indonesian is corrected in every register. English technical nouns are forced
only into **rojak**, the register defined by carrying them. Running that half
over formal and colloquial is what took `fail` from 29,576 raw rows to 29 and
made the BM eval set measure rojak by accident — see the "Known defect"
section of [`../RESULTS.md`](../RESULTS.md). `test_stoplist.py` is the guard.

Eval set (300 InterCode-ALFA prompts, colloquial only):

```
python3 registers.py --in raw/nl2sh_test.csv --out out/eval_bm.jsonl --eval
python3 stoplist.py out/eval_bm.jsonl out/eval_bm.clean.jsonl   # eval gets stoplisted too
```

Hand review sample:

```
shuf -n 200 out/rows.clean.jsonl | python3 -c "import json,sys; [print(json.loads(l)['register'],'|',json.loads(l)['nl']) for l in sys.stdin]"
```

Reads like a government circular → pipeline broken, fix before scaling.

## Row schema

```json
{"id": "nl2sh:1042", "register": "colloquial", "nl": "camne nak cari file lagi besar dari 100MB", "cmd": "find . -size +100M"}
```

`register` ∈ formal | colloquial | rojak | english. `cmd` byte-identical to
source, all four rows. No `target` (shell/OS context) field: three shipped
models never needed one, and adding it means every row changes and a run
to measure it (decided in #49).

## Translation route

Local LLM on the 3090 via any OpenAI-compatible endpoint (llama-server or
vLLM), `--endpoint http://127.0.0.1:8091/v1/chat/completions`. No external
API: no terms-on-derived-datasets problem, nothing to record in NOTICE beyond
the model licence, and the whole 125k run is free.

## How Malaysians actually type a question (issue #41, work item 2)

Everything below is one contributor's judgement plus what the pool and the
probe already showed. It is a hypothesis sheet, not a corpus finding: the
authentic distribution comes from [`survey.md`](survey.md) (direct
solicitation, ~20 beginners × 30 tasks) and, long-term, from #35. Each row
says what would change if it is wrong.

### Nouns: which stay English, which are said in Malay

| stays English when typed | genuinely said in Malay | both, by speaker |
|---|---|---|
| file*, folder, port, server, download, upload, install, update, backup, password*, username, link, laptop, PC, WiFi, internet, browser, terminal, command*, script, error, log, zip, image, video, database, app, software, RAM, CPU, disk*, storage, drive, USB, pendrive, screen, keyboard | pengguna (user, formal only), kata laluan (formal), arahan (formal), pelayan (formal), cakera (formal) | fail / file, direktori / folder, ruang / space, salinan / copy, sambungan / connection |

\* `fail`, `kata laluan`, `arahan`, `cakera` are the school/government
register — real in formal writing, rare in a typed chat question. Colloquial
and rojak default to the English noun; formal keeps the Malay one. Run 6's
probe (`bm-vocab` 0.69 → 0.85 once `fail`/`direktori` were in the pool)
shows the model must *understand* the Malay noun even if it is the minority
input. **If the survey shows `fail` in colloquial typed questions above
~10%, colloquial rows in basics.txt should carry it more.**

### Openers and particles

| token | typed? | notes |
|---|---|---|
| `nak` | yes, dominant | *"nak buat file baru"*. Already the pool's most common opener. |
| `macam mana nak` / `mcm mana` / `camne` / `cmne` | yes | The binary name is `camne`, so the opener is often absorbed; `stoplist.py` strips it. Basics keeps a few `macam mana nak …` rows so the model has seen it. |
| `boleh tak` / `boleh x` | yes | *"boleh tak delete file ni"*. Underrepresented — pool has few. |
| `tolong` / `tlg` | yes | Politeness opener; common from beginners talking to a tool. |
| `ke` (question) | yes, sentence-final | *"nginx jalan ke tak"*, *"internet ada ke"*. |
| `je` / `ja` | yes | Softener at the end: *"tunjuk fail txt je"*. |
| `kan` | rare typed | Speech tag; drop. |
| `lah` / `la` | yes but noise | Carries no meaning for the command; `stoplist.py` already strips it. |
| `eh`, `weh`, `bro` | occasional | Address terms; harmless, ignore. |
| `sila` | formal only | Never in a chat question. |

### Typing shortcuts (none were in the pool before basics.txt)

`x` = tak (*"x boleh"*, *"internet x jalan"*), `dgn` = dengan, `tgk` =
tengok, `mcm` = macam, `sy` = saya, `utk` = untuk, `dlm` = dalam, `kt` =
kat, `msk` = masuk, `skrg` = sekarang, `sbb` = sebab, `jgn` = jangan, `bg`
= bagi, `tp` = tapi, `sblm` = sebelum, `sy`/`aku`/`i` = first person, `2` =
reduplication (*"file2"* = file-file). Number-for-word: *"5 file"* rather than
*"lima fail"*.

`probe.py` has a `shortcut` axis for these. **The claim to falsify: the
model reads them without ever having seen them.** If the axis stays low
after run 7, the fix is a substitution pass over colloquial rows
(`tengok`→`tgk` on a fraction), not more hand-writing.

### Homographs

| token | BM sense | EN sense | guard |
|---|---|---|---|
| `fail` | file | to fail | probe HOMOGRAPH block, both directions |
| `main` | play | `git main`, `main.py` | basics has `main.py`, `git checkout main` |
| `kali` | times (×) | Kali Linux | not measured |
| `bila` | when | — | — |
| `pada` | on/at | — | — |
| `sini`/`sana` | here/there | — | — |
| `tak`/`x` | not | `x` as a variable / `7z x` | `7z x` in basics; probe `short-x` axis |

The `fail` guard scored 0.33 BM / 0.67 EN on run 6, i.e. failing both ways.
Basics leans on `fail` in colloquial and formal, so run 7's BM-sense should
rise; EN-sense is a regression check.

### Rojak is not one register

Three things vary and the pool flattens all of them:

1. **How much English.** *"nak delete file ni"* (verb English) vs *"nak buang
   file ni"* (noun English only) vs *"delete this file la"* (English with a
   particle). Basics writes all three; the pool's rojak is mostly the first.
2. **Generation.** Older typers write fuller words and `saya`; younger typers
   write `sy`/`aku`, `x`, `mcm`, drop `nak`. Basics is skewed young because
   the beginner cohort is; the survey should tell us the real spread.
3. **Region.** Northern (*hang*, *pi*), East Coast (*kito*, *demo*), Sabah/
   Sarawak (*bah*, *sia*), Southern/KL standard. Nothing here or in the pool
   handles dialect; that is a solicitation finding, not something to invent.

### Sources, licensing

Pool sources, measured shares and licences: [`NOTICE`](NOTICE). The pool
itself (pool_v7, basics, both eval sets, dataset card) is published at
https://huggingface.co/datasets/opariffazman/camne-pool.

Future colloquial-input sources:

- Direct solicitation: [`survey.md`](survey.md). Own the data; no licence issue.
- [Malaya](https://github.com/mesolitica/malaya) datasets — MIT/CC mixed;
  check per-set before ingesting. Useful for the shortcut lexicon.
- Public dev-community threads (Lowyat forum, r/malaysia) — read for
  patterns, do not scrape or ingest text.
- Telemetry (#35) — the honest long-term source; blocked on an owner
  decision about constraint 4.

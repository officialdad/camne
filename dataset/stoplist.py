#!/usr/bin/env python3
"""Force translated technical nouns back to English in the NL column, then
print colloquial-marker coverage. Never touches cmd. Stdlib only.

  python3 stoplist.py out/rows.jsonl out/rows.clean.jsonl
"""
import json
import re
import sys
from collections import Counter

# BM form -> English form. Longest first so "muat turun" wins over "turun".
# ponytail: flat word-boundary replace on the NL column only; no morphology.
STOPLIST = [
    # Indonesian leaking out of the (ID-heavy) translator model -> BM/English
    ("bagaimana cara", "Bagaimanakah cara"),
    ("terhubung", "bersambung"),
    ("komitmen", "commit"),
    ("pangkalan data", "database"),
    ("antara muka", "interface"),
    ("mengautomatisasi", "mengautomasikan"),
    ("menonaktifkan", "menyahaktifkan"),
    ("memulai", "memulakan"),
    ("antarmuka", "interface"),
    ("perlawanan", "match"),
    ("pelabuhan", "port"),
    ("bendera", "flag"),
    ("baldi", "bucket"),
    ("paketi", "packet"),
    ("paket", "packet"),
    ("bait", "byte"),
    ("kode", "code"),
    ("gimana", "macam mana"),
    ("silakan", "sila"),
    ("berkas", "file"),
    ("unduh", "download"),
    ("unggah", "upload"),
    ("perintah", "command"),
    ("tampilkan", "tunjuk"),
    ("bisa", "boleh"),
    ("nggak", "tak"),
    ("bikin", "buat"),
    ("banget", "sangat"),
    ("kayak", "macam"),
    ("hapus", "buang"),
    ("udah", "dah"),
    ("aja", "je"),
    ("muat turun", "download"),
    ("muat naik", "upload"),
    ("salinan sandaran", "backup"),
    ("kata laluan", "password"),
    ("baris arahan", "command line"),
    ("fail-fail", "file"),
    ("direktori", "folder"),
    ("pelayan", "server"),
    ("mampatkan", "compress"),
    ("mampat", "compress"),
    ("nyahmampat", "extract"),
    ("pemasangan", "installation"),
    ("pasangkan", "install"),
    ("keizinan", "permission"),
    ("kebenaran akses", "permission"),
    ("rangkaian", "network"),
    ("ingatan", "memory"),
    ("memori", "memory"),
    ("proses", "process"),
    ("cakera", "disk"),
    ("sandaran", "backup"),
    ("skrip", "script"),
    ("arahan", "command"),
    ("proses-proses", "process"),
    ("pautan", "link"),
    ("fail", "file"),
]
_SUBS = [(re.compile(r"\b" + re.escape(bm) + r"\b", re.IGNORECASE), en)
         for bm, en in STOPLIST]

MARKERS = ["camne", "macam mana", "mcm mana", "cmne", "nak", "kat", "ni",
           "tu", "je", "dah", "boleh tak", "tolong", "tlg", "tunjuk",
           "buat", "letak", "buang"]


def clean(nl, register):
    if register == "english":
        return nl
    for pat, en in _SUBS:
        nl = pat.sub(en, nl)
    return nl


def main():
    src, dst = sys.argv[1], sys.argv[2]
    marker_hits = Counter()
    changed = colloquial_total = 0
    with open(src, encoding="utf-8") as f, open(dst, "w", encoding="utf-8") as out:
        for line in f:
            row = json.loads(line)
            fixed = clean(row["nl"], row["register"])
            if fixed != row["nl"]:
                changed += 1
                row["nl"] = fixed
            if row["register"] == "colloquial":
                colloquial_total += 1
                low = row["nl"].lower()
                for m in MARKERS:
                    if re.search(r"\b" + re.escape(m) + r"\b", low):
                        marker_hits[m] += 1
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"stoplist fixed {changed} rows -> {dst}")
    if colloquial_total:
        print(f"marker coverage over {colloquial_total} colloquial rows:")
        for m in MARKERS:
            pct = 100 * marker_hits[m] / colloquial_total
            print(f"  {m:12s} {marker_hits[m]:6d}  {pct:5.1f}%")


if __name__ == "__main__":
    main()

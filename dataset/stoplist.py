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

# The binary name IS the question word: `camne <words>` means the model only
# ever sees <words>, so no register keeps a "how do I" opener (owner decision,
# 2026-08-13). Formal drops the interrogative scaffold and flips the leading
# meN- verb to its imperative; colloquial/rojak drop camne/macam-mana forms.
_FORMAL_OPENER = re.compile(
    r"^(bagaimana(kah)?|apakah)\s+((cara|kaedah|langkah)\s+)?(untuk\s+)?", re.IGNORECASE)
_CHAT_OPENER = re.compile(r"^(camne|cmne|macam\s*mana|mcm\s*mana|cammana)[\s,]+", re.IGNORECASE)
_CHAT_TRAILER = re.compile(r"[\s,]+(camne|cmne|macam\s*mana|mcm\s*mana|cammana)\s*[?!.]*$", re.IGNORECASE)

# leading formal verb -> imperative. Curated from the corpus (top forms cover
# >90% of formal rows); unmapped meN- words stay as-is — safe, just stilted.
# ponytail: a lexicon-free meN- peeler is ambiguous (mengira->kira but
# mengambil->ambil); curate instead, extend when coverage stats say so.
VERB_MAP = {
    "mencari": "cari", "memaparkan": "paparkan", "mencetak": "cetak",
    "menjalankan": "jalankan", "memulakan": "mulakan",
    "menyenaraikan": "senaraikan", "membuat": "buat",
    "mendapatkan": "dapatkan", "menghasilkan": "hasilkan",
    "menetapkan": "tetapkan", "memilih": "pilih",
    "menghapuskan": "hapuskan", "membuka": "buka", "melihat": "lihat",
    "menggunakan": "gunakan", "menyalin": "salin", "mengubah": "ubah",
    "memasang": "pasang", "menukar": "tukar", "menggantikan": "gantikan",
    "mengekstrak": "ekstrak", "menghantar": "hantar",
    "mengaktifkan": "aktifkan", "menambahkan": "tambahkan",
    "memeriksa": "periksa", "melaksanakan": "laksanakan",
    "mengambil": "ambil", "menunjukkan": "tunjukkan",
    "memadamkan": "padamkan", "memadam": "padam", "menyemak": "semak",
    "menghentikan": "hentikan", "mengeluarkan": "keluarkan",
    "menyimpan": "simpan", "menutup": "tutup", "mengira": "kira",
    "menambah": "tambah", "membuang": "buang", "memuatkan": "muatkan",
    "menyahaktifkan": "nyahaktifkan", "mengemaskini": "kemas kini",
    "memaparkan semula": "paparkan semula", "menyaring": "saring",
    "menapis": "tapis", "mengedit": "edit", "menguji": "uji",
    "mengesahkan": "sahkan", "mengalihkan": "alihkan",
    "memindahkan": "pindahkan", "menyambung": "sambung",
}


def _deopener(nl, register):
    if register == "formal":
        stripped = _FORMAL_OPENER.sub("", nl).strip()
        if stripped and stripped != nl:
            words = stripped.split()
            head = words[0].lower()
            if head in VERB_MAP:
                words[0] = VERB_MAP[head]
            nl = " ".join(words)
            nl = nl[0].upper() + nl[1:]
            nl = nl.rstrip("?").rstrip()
        return nl
    # colloquial / rojak
    nl = _CHAT_OPENER.sub("", nl).strip()
    nl = _CHAT_TRAILER.sub("", nl).strip()
    return nl


def clean(nl, register):
    if register == "english":
        return nl
    for pat, en in _SUBS:
        nl = pat.sub(en, nl)
    return _deopener(nl, register)


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

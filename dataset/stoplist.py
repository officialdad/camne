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
    # Affixed forms of the entries below: \b + a bare stem misses every
    # prefixed/derived form the translator emits, so they are listed out.
    ("memuat turun", "download"),
    ("memuat naik", "upload"),
    ("frasa sandi", "passphrase"),
    ("kata sandi", "password"),
    ("mengunduh", "download"),
    ("mengunggah", "upload"),
    ("menampilkan", "tunjuk"),
    ("memperbarui", "update"),
    ("pembaruan", "update"),
    ("perbarui", "update"),
    ("mengurutkan", "susun"),
    ("diurutkan", "disusun"),
    ("urutkan", "susun"),
    ("menghapus", "membuang"),
    ("dihapus", "dibuang"),
    ("direktori-direktori", "folder"),
    ("folder-folder", "folder"),
    ("berkas-berkas", "file"),
    # Indonesian the first pass missed
    ("mengkompilasi", "compile"),
    ("mengkonversi", "convert"),
    ("mengonversi", "convert"),
    ("mengonsumsi", "guna"),
    ("menginstal", "install"),
    ("pemindaian", "scan"),
    ("pengaturan", "setting"),
    ("penyimpanan", "storage"),
    ("otentikasi", "authentication"),
    ("perangkat", "device"),
    ("pratinjau", "preview"),
    ("kontainer", "container"),
    ("tumpukan", "stack"),
    ("memindai", "scan"),
    ("ekstensi", "extension"),
    ("peluasan", "extension"),
    ("keluaran", "output"),
    ("konversi", "convert"),
    ("jaringan", "network"),
    ("masukan", "input"),
    ("tampilan", "paparan"),
    ("tautan", "link"),
    ("setelan", "setting"),
    ("binaari", "binary"),
    ("peranti", "device"),
    ("instal", "install"),
    ("kolom", "column"),
    ("wadah", "container"),
    ("pesan", "message"),
    ("trus", "terus"),
    ("nih", "ni"),
    ("tuh", "tu"),
    # Technical nouns a Malaysian in a terminal says in English, which the
    # translator "corrected" into textbook BM
    ("ungkapan biasa", "regex"),
    ("repositori", "repo"),
    ("rentetan", "string"),
    ("tetingkap", "window"),
    ("cangkang", "shell"),
    ("cawangan", "branch"),
    ("pengguna", "user"),
    ("partisi", "partition"),
    ("senarai", "list"),
    ("laluan", "path"),
    ("storan", "storage"),
    ("corak", "pattern"),
    ("ralat", "error"),
    ("imej", "image"),
    ("hos", "host"),
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
    r"^((sila|mohon)\s+(nyatakan|jelaskan|terangkan|tunjukkan)\s+)?"
    r"(bagaimana(kah)?|apakah)\s+((cara|kaedah|langkah)\s+)?((saya|kita|anda)\s+)?"
    r"((boleh|dapat|hendak|untuk)\s+)?(untuk\s+)?", re.IGNORECASE)
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
    "memuat": "muat", "membaca": "baca", "membina": "bina",
    "menentukan": "tentukan", "melakukan": "lakukan",
    "menggabungkan": "gabungkan", "menulis": "tulis", "memaksa": "paksa",
    "melancarkan": "lancarkan", "membandingkan": "bandingkan",
    "mengakses": "akses", "membatalkan": "batalkan", "mencipta": "cipta",
    "membersihkan": "bersihkan", "memulihkan": "pulihkan",
    "memotong": "potong", "memasukkan": "masukkan",
    "menganalisis": "analisis", "mengemas": "kemas", "mengabaikan": "abaikan",
    "memantau": "pantau", "membahagikan": "bahagikan",
    "menukarkan": "tukarkan", "memainkan": "mainkan",
    "melampirkan": "lampirkan", "membunuh": "bunuh", "membatasi": "hadkan",
    # ID-flavoured verbs whose Malaysian form is the English one
    "mengkompres": "compress", "mengarsipkan": "archive",
    "mengeksport": "export", "mengimport": "import", "mengklon": "clone",
    "mengkonfigurasi": "configure", "memformat": "format",
    "menerapkan": "gunakan", "mengacak": "rawakkan",
    "memverifikasi": "verify", "memvalidasi": "validate",
    "mengupgrade": "upgrade", "mengkompresi": "compress",
    "memutakhirkan": "update", "mengimbas": "scan",
    "menghitung": "kira", "membagi": "bahagi", "membahagi": "bahagi",
    "memutar": "putar", "menandai": "tandakan",
    "meningkatkan": "tingkatkan", "membalikkan": "balikkan",
    "mengikat": "ikat", "mengakhiri": "akhiri", "mengurangkan": "kurangkan",
    "mematikan": "matikan", "mengunci": "kunci", "menangkap": "tangkap",
    "memberikan": "berikan", "melaporkan": "laporkan",
    "mengecualikan": "kecualikan", "memastikan": "pastikan",
    "melepaskan": "lepaskan", "menerbitkan": "terbitkan",
    "mewujudkan": "wujudkan", "membenarkan": "benarkan",
}

# ponytail: curated map covers the top ~45 leading forms (~11% of formal rows);
# the ~300-form tail stays meN- and merely stilted. Upgrade path is a corpus
# frequency check on candidate peels, not a hand-written lexicon.

# Every row is what follows `camne` — a question. Malaysians do not put lah/la/
# ah on a question, so the particle is wrong in all of them, not merely overused
# (owner decision, 2026-08-13). The translator emitted "lah" on 89% of rojak.
# Leading \s+ or start only: `ls -la` is a flag, not a particle.
_LAH = re.compile(r"(?:^|\s+)(?:lah|la|ah)\b", re.IGNORECASE)


def _deopener(nl, register):
    if register == "formal":
        stripped = _FORMAL_OPENER.sub("", nl).strip()
        touched = bool(stripped) and stripped != nl
        if stripped:
            nl = stripped
        # imperative register: flip the leading meN- verb whether or not an
        # interrogative opener was there to strip.
        words = nl.split()
        if words and words[0].lower() in VERB_MAP:
            words[0] = VERB_MAP[words[0].lower()]
            nl = " ".join(words)
            touched = True
        if touched:
            nl = nl.rstrip("?").rstrip()
        return nl
    # colloquial / rojak
    nl = _CHAT_OPENER.sub("", nl).strip()
    nl = _CHAT_TRAILER.sub("", nl).strip()
    stripped = _LAH.sub("", nl).strip()
    if stripped:  # a row that was nothing but the particle keeps its text
        nl = stripped
    # "boleh tak, lah?" must not leave "boleh tak,?"
    return re.sub(r"\s*,\s*(?=[?!.]|$)", "", nl)


# Translator sometimes injects slang profanity as rojak flavour ("..., sial").
# Beginner-facing dataset: strip it. "fuck" survives only when the command
# itself contains it (the `thefuck` tool) — checked in clean() below.
_PROFANITY = re.compile(
    r"[\s,]*\b(sial(-sial)?|shit|damn|bodoh|celaka|pukimak|babi)\b[\s,]*",
    re.IGNORECASE)
_FUCK = re.compile(r"\bfuck\b", re.IGNORECASE)


def clean(nl, register, cmd=""):
    if register == "english":
        return nl
    was_upper = nl[:1].isupper()
    for pat, en in _SUBS:
        nl = pat.sub(en, nl)
    nl = _PROFANITY.sub(" ", nl).strip(" ,")
    if _FUCK.search(nl) and not _FUCK.search(cmd):
        nl = _FUCK.sub("", nl).strip(" ,")
    nl = re.sub(r"\s{2,}", " ", nl)
    nl = _deopener(nl, register)
    # a lowercase replacement or a peeled verb must not decapitalise the row
    if register == "formal" and was_upper and nl[:1].islower():
        nl = nl[0].upper() + nl[1:]
    return nl


def main():
    src, dst = sys.argv[1], sys.argv[2]
    marker_hits = Counter()
    changed = colloquial_total = 0
    with open(src, encoding="utf-8") as f, open(dst, "w", encoding="utf-8") as out:
        for line in f:
            row = json.loads(line)
            fixed = clean(row["nl"], row["register"], row.get("cmd", ""))
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

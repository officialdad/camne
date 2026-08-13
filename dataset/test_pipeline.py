#!/usr/bin/env python3
"""Smallest checks that fail if the pipeline logic breaks. Stdlib only.

  python3 test_pipeline.py
"""
import json
import os
import tempfile

from stoplist import clean
from verify import check

# --- stoplist ---------------------------------------------------------------
assert clean("camne nak padam fail ni", "colloquial") == "nak padam file ni"
assert clean("sila muat turun fail itu dari pelayan", "formal") == \
    "sila download file itu dari server"
# longest-first: "muat turun" must not decay via a shorter rule
assert "download" in clean("muat turun", "rojak")
# word boundary: "failed" (inside rojak English) must not become "fileed"
assert clean("job tu failed ke", "rojak") == "job tu failed ke"
# english register untouched even if it contains a BM-looking word
assert clean("delete the fail log", "english") == "delete the fail log"
# Indonesian -> BM/English
# gimana -> macam mana (ID fix), which is then stripped as an opener
assert clean("gimana bisa hapus berkas ini", "colloquial") == "boleh buang file ini"
# translated technical nouns forced back to English
assert clean("padam baldi S3 di pelabuhan 8080", "formal") == \
    "padam bucket S3 di port 8080"
assert clean("panjang paketi dalam bait", "formal") == "panjang packet dalam byte"
# ...but valid BM containing an ID word as substring stays intact
# "hapus" inside "menghapuskan" has no word boundary, so the ID rule stays put;
# only the imperative flip touches it
assert clean("menghapuskan password", "formal") == "hapuskan password"
assert clean("saja sudah", "colloquial") == "saja sudah"

# --- opener stripping (binary name carries the question word) ---------------
assert clean("Bagaimanakah cara untuk mencari file melebihi 100MB?", "formal") == \
    "Cari file melebihi 100MB"
assert clean("Bagaimana untuk memaparkan ruang kosong?", "formal") == \
    "Paparkan ruang kosong"
# unmapped leading verb survives un-peeled, opener still gone
assert clean("Apakah cara untuk mengarkibkan folder ini?", "formal") == \
    "Mengarkibkan folder ini"
# non-interrogative formal rows untouched
assert clean("Sila nyatakan nombor port destinasi.", "formal") == \
    "Sila nyatakan nombor port destinasi."
assert clean("macam mana nak check disk space kat sini", "rojak") == \
    "nak check disk space kat sini"
assert clean("camne nak tengok free space?", "colloquial") == "nak tengok free space?"
assert clean("nak tengok file terbuka tu camne?", "colloquial") == "nak tengok file terbuka tu"
# "macam" alone (comparison, not opener) untouched
assert clean("buat file baru macam contoh ni", "colloquial") == "buat file baru macam contoh ni"
# interrogative scaffold with a pronoun in it
assert clean("Bagaimana saya boleh memadam file ini?", "formal") == "Padam file ini"
# polite scaffold wrapped around the interrogative
assert clean("Sila nyatakan bagaimana untuk menyimpan hasil.", "formal") == \
    "Simpan hasil."
# "sila" without an interrogative behind it is a normal request, left alone
assert clean("Sila nyatakan nombor port.", "formal") == "Sila nyatakan nombor port."

# --- formal is imperative even with no opener to strip ---------------------
assert clean("Menulis output ke file log", "formal") == "Tulis output ke file log"
# a lowercase stoplist replacement must not decapitalise the row
assert clean("Memperbarui definisi virus", "formal") == "Update definisi virus"
# unmapped meN- verb still survives (ceiling of the curated map)
assert clean("Mengarkibkan folder ini", "formal") == "Mengarkibkan folder ini"

# --- affixed Indonesian forms the bare-stem rules missed --------------------
assert clean("Mengunduh dan menghapus berkas lama", "formal") == \
    "Download dan membuang file lama"
assert clean("Memuat turun laporan ini", "formal") == "Download laporan ini"
assert clean("cari regex je dalam folder-folder tu", "colloquial") == \
    "cari regex je dalam folder tu"
# technical nouns the translator "corrected" into textbook BM
assert clean("Senaraikan pengguna dalam repositori", "formal") == \
    "Senaraikan user dalam repo"

# --- lah/la/ah never belong on a question -----------------------------------
assert clean("nak check disk space lah", "rojak") == "nak check disk space"
assert clean("run the tests lah using this config", "rojak") == "run the tests using this config"
assert clean("zip PNG ni, save kat path tu lah?", "colloquial") == "zip PNG ni, save kat path tu?"
assert clean("check domain info la", "rojak") == "check domain info"
assert clean("nak document this example ah", "rojak") == "nak document this example"
# a word merely ending in the particle is not the particle
assert clean("check kalau ada yang salah", "rojak") == "check kalau ada yang salah"
assert clean("nak tengok apa yang telah berubah", "colloquial") == "nak tengok apa yang telah berubah"
# neither is the flag in `ls -la` / `ls -lah`
assert clean("nak run ls -lah kat sini lah", "rojak") == "nak run ls -lah kat sini"
assert clean("nak run ls -la la", "rojak") == "nak run ls -la"
# the comma that carried the particle goes with it
assert clean("set watak ASCII output boleh tak, lah?", "colloquial") == \
    "set watak ASCII output boleh tak?"

# --- profanity filler --------------------------------------------------------
assert clean("nak tengok lock semua, sial", "rojak") == "nak tengok lock semua"
assert clean("set alias fuck jadi thefuck", "colloquial",
             cmd="eval $(thefuck --alias fuck)") == "set alias fuck jadi thefuck"
assert clean("apa shit ni, list file je", "rojak") == "apa ni, list file je"

# --- tldr -------------------------------------------------------------------
from tldr import parse_page

PAGE = """# touch

> Create files and set access/modification times.

- Create specific files:

`touch {{path/to/file1}} {{path/to/file2}}`

- Set the times on a file to a specific date and time:

`touch -t {{YYYYMMDDHHMM.SS}} {{path/to/file}}`
"""
got = parse_page(PAGE, "touch")
assert got[0] == ("Create specific files", "touch path/to/file1 path/to/file2"), got[0]
assert len(got) == 2 and "{{" not in got[1][1]
# description kept verbatim, no tool-name leak
got = parse_page("- Start the daemon:\n\n`redis-server`\n", "redis-server")
assert got == [("Start the daemon", "redis-server")], got

# --- verify -----------------------------------------------------------------
def rows_file(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for r in rows:
        f.write(json.dumps(r) + "\n")
    f.close()
    return f.name

src = {"t:0": "rm -rf ./build"}
good = [{"id": "t:0", "register": reg, "nl": "x", "cmd": "rm -rf ./build"}
        for reg in ("formal", "colloquial", "rojak", "english")]

p = rows_file(good)
assert check(src, p) == [], check(src, p)
os.unlink(p)

drifted = [dict(r) for r in good]
drifted[1]["cmd"] = "rm -rf /build"  # one byte off
p = rows_file(drifted)
assert any("drifted" in e for e in check(src, p))
os.unlink(p)

missing = good[:2]  # formal+colloquial only
p = rows_file(missing)
assert any("missing registers" in e for e in check(src, p))
os.unlink(p)

eval_only = [{"id": "t:0", "register": "colloquial", "nl": "x", "cmd": "rm -rf ./build"}]
p = rows_file(eval_only)
assert check(src, p) == []  # colloquial-only file is a valid eval set
os.unlink(p)

dup = good + [good[0]]
p = rows_file(dup)
assert any("duplicate" in e for e in check(src, p))
os.unlink(p)

print("ok: all pipeline checks pass")

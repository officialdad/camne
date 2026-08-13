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
assert clean("menghapuskan password", "formal") == "menghapuskan password"
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

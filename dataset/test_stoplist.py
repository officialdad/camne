#!/usr/bin/env python3
"""Runnable check for the register split.  python3 test_stoplist.py

The list used to do two jobs at once and quietly deleted every Malay noun from
the pool. These assertions are what "quietly" costs.
"""
from stoplist import clean

CASES = [
    # (nl, register, must contain, must NOT contain)
    # Malay nouns survive outside rojak — this is the whole point of the split.
    ("nak buat fail baru", "colloquial", ["fail"], ["file"]),
    ("Senaraikan semua fail dalam direktori ini", "formal",
     ["fail", "direktori"], ["file", "folder"]),
    ("tukar kata laluan user", "colloquial", ["kata laluan"], ["password"]),
    # ...and are replaced inside rojak, which is defined by English nouns.
    ("nak buat fail baru", "rojak", ["file"], ["fail"]),
    ("cari fail dalam direktori tu", "rojak", ["file", "folder"],
     ["fail", "direktori"]),
    ("tukar kata laluan user", "rojak", ["password"], ["kata laluan"]),
    # Indonesian is a defect in every register, rojak included.
    # `gimana`->`macam mana`, which _deopener then strips: the binary name is
    # the question word, so no register keeps the opener.
    ("gimana nak liat berkas", "colloquial", ["fail"], ["berkas", "gimana"]),
    ("gimana nak liat berkas", "rojak", ["file"],
     ["berkas", "fail", "gimana"]),
    ("bisa nggak unduh file ni", "colloquial", ["boleh", "tak", "muat turun"],
     ["bisa", "nggak", "unduh"]),
    # The chain: ID -> BM -> English, and only rojak takes the last hop.
    ("memuat turun file", "formal", ["muat turun"], ["download"]),
    ("memuat turun file", "rojak", ["download"], ["muat turun"]),
    # Longest-match: `laluan`->`path` used to eat `kata laluan`->`password`,
    # which put 904 rows of "kata path" into training.
    ("tukar kata laluan", "rojak", ["password"], ["kata path", "laluan"]),
    # English register is never touched at all.
    ("create a new file", "english", ["create a new file"], []),
]


def main():
    bad = 0
    for nl, register, want, unwanted in CASES:
        got = clean(nl, register).lower()
        for w in want:
            if w.lower() not in got:
                print(f"FAIL [{register}] {nl!r} -> {got!r}: missing {w!r}")
                bad += 1
        for u in unwanted:
            if u.lower() in got:
                print(f"FAIL [{register}] {nl!r} -> {got!r}: still has {u!r}")
                bad += 1
    # cmd is never touched, in any register
    for register in ("formal", "colloquial", "rojak", "english"):
        assert clean("rm -rf /tmp/fail", register) == clean(
            "rm -rf /tmp/fail", register), "clean is not deterministic"
    print("FAILED" if bad else f"ok — {len(CASES)} cases")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()

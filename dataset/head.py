#!/usr/bin/env python3
"""Grow the head of the pool for the beginner verbs (issue #62). Stdlib only.

  python3 head.py out/pool_v7.jsonl out/pool_v8.jsonl

Run 9 capped the tail and `git` went 4.3% -> 5.8% of the pool; `delete
file` came back `git obliterate` and `list processes` `pm2`. `nano` has 53
rows, `less` 90, `ps` 880 against `git` 13k. Nothing in the sources fills
that: the rows prior.py dropped for these tools are tldr placeholders whose
NL never named the file, and the rows disambiguate.py dropped are pipe
one-liners. So the head is written, basics.txt style, in basics_head.txt:
same block format plus slots -- `{f}` any file, `{t}` text file, `{d}`
folder, `{u}` user, `{h}` host, `{n}` count, `{pid}`, `{p}` process, `{z}`
zip, `{url}`, `{port}`, `{sshport}`, `{log}` -- filled from NAMES, K expansions per block, the
k-th name of every list, so `rm {f}` / `nak buang fail {f}` becomes twenty
consistent pairs. A phrasing must carry every slot its cmd carries: a row
whose NL never names what the command names is the placeholder bug again.

Budget per tool: min(CAP, TARGET - real rows), real = rows in the source
pool whose id is not an augment_verbs `+verb` or rebalance `~i` duplicate;
tools at or above TARGET get nothing. Whole tasks (one expansion of one
block, all registers) are sampled with prior.sample_ids, seed 42. CAP is
`mkdir`'s row count in pool_v7 so no single tool jumps past the head it is
meant to join. Tools the probe holds out (training/probe.py HOLDOUT) are
refused: a head row for `chsh` would un-hold it.

Issue #51 rides along: the translation step turned `file.txt` in the NL
into `fail.txt` while the command kept `file.txt`, and the model learned
Malay-name -> English-name as a mapping. Where a non-English row's command
names exactly one file the NL does not, and the NL names exactly one file
the command does not whose stem is the Malay of it (`fail1.csv` for
`file1.csv`, `dokumen.zip` for `documents.zip`), the NL gets the command's
name back. Commands are never touched. Every slot list carries Malay
filenames (lama.txt, nota.txt, laporan.pdf, projek) byte-identical on both
sides, which is the positive example the pool never had.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

from basics import parse
from prior import sample_ids
from rebalance import tool

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET, SEED = 1000, 42
# tools training/probe.py HOLDOUT measures generalisation on; keep them unwritten
HOLDOUT = {"truncate", "tac", "whereis", "dirname", "tee", "timeout", "chsh",
           "printenv", "nl"}

NAMES = {
    "t": "baru.txt nota.txt lama.txt laporan.txt senarai.txt surat.txt jadual.csv "
         "data.csv todo.md catatan.md draf.txt minit.txt ucapan.txt config.yaml "
         "index.html main.py skrip.sh output.log error.log resit.txt".split(),
    "f": "laporan.pdf gambar.jpg nota.txt lama.txt foto.png resume.docx senarai.txt "
         "video.mp4 muzik.mp3 slaid.pptx notes.txt data.csv borang.pdf sijil.pdf "
         "logo.png tesis.docx jadual.xlsx surat.txt cover.jpg dokumen.pdf".split(),
    "d": "projek dokumen gambar backup tugasan kerja arkib muzik laporan Downloads "
         "Documents src data foto nota video projek_lama sekolah kuliah borang".split(),
    "u": "ariff ali siti root admin aiman farah hafiz nurul amir azman mei kumar "
         "danial aina hana izzat www-data ubuntu pi".split(),
    "h": "192.168.1.10 192.168.0.20 10.0.0.12 server.local example.com myserver.com "
         "172.16.0.3 pi.local 203.0.113.7 vps.example.com 10.1.1.4 192.168.1.100 "
         "dev.example.com 10.0.1.9 staging.local 192.168.100.5 host.example.org "
         "10.10.10.10 nas.local 172.20.0.8".split(),
    "n": "10 20 5 50 100 3 15 30 25 40 8 12 200 7 60 2 500 1000 45 90".split(),
    "pid": "1234 5678 2201 987 4410 3345 1502 7788 6001 2048 913 3210 4499 1867 "
           "7002 2555 8123 640 3999 5150".split(),
    "p": "nginx python3 node firefox chrome mysql docker sshd apache2 java code vim "
         "redis postgres php ffmpeg spotify slack gnome-shell bash".split(),
    "z": "backup.zip gambar.zip projek.zip dokumen.zip arkib.zip laporan.zip data.zip "
         "foto.zip tugasan.zip source.zip kerja.zip muzik.zip borang.zip notes.zip "
         "release.zip sekolah.zip kuliah.zip video.zip resit.zip slaid.zip".split(),
    "url": ["https://example.com/" + x for x in
            "laporan.pdf data.csv setup.sh gambar.jpg backup.zip notes.txt video.mp4 "
            "app.tar.gz index.html muzik.mp3 borang.pdf foto.png data.json release.zip "
            "config.yaml tesis.docx logo.png senarai.txt skrip.sh arkib.zip".split()],
    "port": "22 2222 8080 3000 5000 443 80 8000 2200 9000 5432 3306 6379 8443 "
            "22022 4000 8888 1234 7000 8081".split(),
    "sshport": "2222 2200 22022 2202 8022 2022 10022 2223 2224 22222 4422 2233 "
               "2244 2255 2266 2277 2288 2299 6222 22".split(),
    "log": "output.log error.log access.log debug.log system.log nginx.log build.log "
           "install.log backup.log sync.log cron.log worker.log api.log db.log "
           "test.log deploy.log run.log update.log service.log audit.log".split(),
}
K = 20
assert all(len(v) == K for v in NAMES.values())
SLOT = re.compile(r"\{(t2|t|f2|f|d2|d|u|h|n|pid|sshport|port|p|z|url|log)\}")


def fill(text, k):
    """Slot k of every list; `{t2}`/`{f2}`/`{d2}` are the same lists shifted by 7."""
    def one(m):
        s = m.group(1)
        return NAMES[s[0]][(k + 7) % K] if s in ("t2", "f2", "d2") else NAMES[s][k % K]
    return SLOT.sub(one, text)


def expand(path):
    """basics_head.txt -> [(task_id, cmd, {register: [nl]})], slots filled."""
    out = []
    for b, (cmd, regs) in enumerate(parse(path)):
        slots = set(SLOT.findall(cmd))
        if tool(cmd) in HOLDOUT:
            raise ValueError(f"{cmd!r}: {tool(cmd)} is a probe HOLDOUT tool")
        for reg, phrs in regs.items():
            for p in phrs:
                if slots - set(SLOT.findall(p)):
                    raise ValueError(f"{cmd!r}: {reg} phrasing {p!r} misses a slot")
        for k in range(K if slots else 1):
            out.append((f"head:{b}.{k}", fill(cmd, k),
                        {reg: [fill(p, k) for p in phrs] for reg, phrs in regs.items()}))
    return out


def rows(path):
    for tid, cmd, regs in expand(path):
        for reg, phrs in regs.items():
            for j, nl in enumerate(phrs):
                yield {"id": f"{tid}.{j}", "register": reg, "nl": nl, "cmd": cmd}


def real(pool):
    """Rows per tool, augment_verbs / rebalance duplicates not counted."""
    return Counter(tool(r["cmd"]) for r in pool
                   if "+" not in r["id"] and "~" not in r["id"])


def budget(pool, cap):
    return {t: min(cap, TARGET - n) for t, n in real(pool).items() if n < TARGET}


def pick(head, budgets):
    """Head rows cut to budget per tool, whole tasks, seed 42; no budget, no rows."""
    by_tool = defaultdict(list)
    for r in head:
        by_tool[tool(r["cmd"])].append(r)
    keep = set()
    for t, rs in sorted(by_tool.items()):
        tasks = [{**r, "id": r["id"].rsplit(".", 1)[0]} for r in rs]
        want = budgets.get(t, 0)
        keep |= sample_ids(tasks, want, SEED)
    return [r for r in head if r["id"].rsplit(".", 1)[0] in keep]


# --- issue #51 -------------------------------------------------------------
FILENAME = re.compile(r"(?<![\w/.%$-])([A-Za-z][\w-]*\.(?:txt|pdf|csv|log|md|jpg|"
                      r"jpeg|png|gif|zip|tar|gz|sh|py|json|xml|html|conf|cfg|bak|"
                      r"doc|docx|xls|xlsx|ppt|pptx|mp3|mp4|iso|deb))\b")


# stems the translator produced in the NL for a name the command spells in English
STEM = {"fail": "file", "dokumen": "documents", "teks": "text", "senarai": "list",
        "arkib": "archive", "arsip": "archive", "sumber": "source", "dalam": "in",
        "luar": "out"}


def restore_name(nl, cmd):
    """NL with the command's filename back where the translator renamed it."""
    c, l = set(FILENAME.findall(cmd)), set(FILENAME.findall(nl))
    miss, extra = c - l, l - c
    if len(miss) == 1 and len(extra) == 1:
        (m,), (e,) = miss, extra
        for bm, en in STEM.items():
            if e.startswith(bm) and en + e[len(bm):] == m:
                return nl.replace(e, m)
    return nl


def report(label, pool):
    cnt = Counter(tool(r["cmd"]) for r in pool)
    top30 = sum(n for _, n in cnt.most_common(30))
    print(f"{label}: {len(pool)} rows, {len(cnt)} first tokens, "
          f"top-30 share {100*top30/len(pool):.1f}%, "
          f"git {100*cnt['git']/len(pool):.1f}%, find {100*cnt['find']/len(pool):.1f}%")
    return cnt


def main():
    src, dst = sys.argv[1], sys.argv[2]
    head_txt = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "basics_head.txt")
    pool = [json.loads(l) for l in open(src, encoding="utf-8")]
    before = report("before", pool)
    cap = before["mkdir"]

    renamed = 0
    for r in pool:
        if r["register"] != "english":
            nl = restore_name(r["nl"], r["cmd"])
            renamed += nl != r["nl"]
            r["nl"] = nl

    head = list(rows(head_txt))
    budgets = budget(pool, cap)
    added = pick(head, budgets)
    out = pool + added
    after = report("after", out)

    print(f"#51 filenames restored in NL: {renamed}; head written {len(head)}, "
          f"added {len(added)} (cap {cap}, target {TARGET})")
    print(f"{'tool':10} {'v7':>6} {'real':>6} {'budget':>6} {'added':>6} {'v8':>6}")
    got = Counter(tool(r["cmd"]) for r in added)
    for t in sorted({tool(r["cmd"]) for r in head}, key=lambda t: -got[t]):
        print(f"{t:10} {before[t]:>6} {real(pool)[t]:>6} {budgets.get(t, 0):>6} "
              f"{got[t]:>6} {after[t]:>6}")
    with open(dst, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} rows -> {dst}")


if __name__ == "__main__":
    main()

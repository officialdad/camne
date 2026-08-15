#!/usr/bin/env python3
"""Grid probe: which *phrasing* of the same task does the model survive?

  python3 probe.py                      # shipped model, pinned llama build
  python3 probe.py --model X.gguf

InterCode-ALFA measures whether camne can do a task. This measures whether it
can still do a task it already knows when the user says it a different way —
a different verb, the Malay noun instead of the English one, a count, a
different register. Those are the axes real users vary and the benchmark
holds fixed.

Scoring is tool-level on purpose: "did it reach for touch/mkdir/rm" is coarse,
but it is unambiguous and needs no container, so the whole grid runs in two
minutes and the per-axis breakdown is the actual output. A wrong flag on the
right tool counts as a pass here; ALFA is what catches that.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import time
import urllib.request

SYSTEM = ("You are a shell command generator. Output exactly one line: a "
          "single POSIX/bash command that accomplishes the user's request. "
          "No prose, no markdown fences, no explanation.")
PORT = 18095

PINNED = os.path.expanduser("~/.cache/camne/bin/llama-b10333/llama-server")
MODEL = os.path.expanduser("~/.cache/camne/models/camne-1.5b-Q4_K_M.gguf")

# Each task: the tool that answers it, then the same request in many phrasings.
# axis names are what the report groups by.
TASKS = [
    {
        "task": "create file",
        "ok": r"\b(touch|tee|>\s*\S|printf|cat\s*>)",
        "p": {
            "en": "create a new file",
            "rojak": "nak create file baru",
            "collo-buat-file": "nak buat file baru",
            "collo-buat-fail": "nak buat fail baru",
            "collo-cipta-file": "nak cipta file baru",
            "collo-cipta-fail": "nak cipta fail baru",
            "formal": "Buat satu file baharu",
            "count-en": "create 5 files",
            "count-file": "nak cipta 5 file",
            "count-fail": "nak cipta 5 fail",
        },
    },
    {
        "task": "create folder",
        "ok": r"\bmkdir\b",
        "p": {
            "en": "create a new folder",
            "rojak": "nak create folder baru",
            "collo-buat": "nak buat folder baru",
            "collo-cipta": "nak cipta satu folder",
            "collo-direktori": "nak buat direktori baru",
            "formal": "Buat satu folder baharu",
            "count-en": "create 5 folders",
            "count-bm": "nak buat 5 folder",
        },
    },
    {
        "task": "delete file",
        "ok": r"\b(rm|unlink|shred)\b",
        "p": {
            "en": "delete a file",
            "rojak": "nak delete file ni",
            "collo-buang": "nak buang file ni",
            "collo-padam": "nak padam file ni",
            "collo-fail": "nak buang fail ni",
            "formal": "Hapuskan file tersebut",
        },
    },
    {
        "task": "list files",
        "ok": r"\b(ls|find|dir)\b",
        "p": {
            "en": "list files here",
            "rojak": "nak list file kat sini",
            "collo-tunjuk": "tunjuk semua file kat sini",
            "collo-senarai": "nak senarai semua fail",
            "formal": "Senaraikan semua file dalam folder ini",
        },
    },
    {
        "task": "copy file",
        "ok": r"\b(cp|rsync|install)\b",
        "p": {
            "en": "copy a file to /tmp",
            "rojak": "nak copy file ni ke /tmp",
            "collo-salin": "nak salin file ni ke /tmp",
            "collo-fail": "nak copy fail ni ke /tmp",
            "formal": "Salin file ini ke /tmp",
        },
    },
    {
        "task": "rename file",
        "ok": r"\b(mv|rename)\b",
        "p": {
            "en": "rename a file",
            "rojak": "nak rename file ni",
            "collo-tukar": "nak tukar nama file ni",
            "collo-fail": "nak tukar nama fail ni",
            "formal": "Tukar nama file tersebut",
        },
    },
    {
        "task": "disk space",
        "ok": r"\b(df|du|lsblk)\b",
        "p": {
            "en": "check free disk space",
            "rojak": "nak check disk space",
            "collo-tengok": "nak tengok baki space",
            "collo-cakera": "nak tengok ruang cakera",
            "formal": "Tunjukkan ruang disk yang masih kosong",
        },
    },
    {
        "task": "list processes",
        "ok": r"\b(ps|top|htop|pgrep)\b",
        "p": {
            "en": "list running processes",
            "rojak": "nak list semua process",
            "collo": "tunjuk process yang tengah jalan",
            "formal": "Senaraikan semua process yang sedang berjalan",
        },
    },
    {
        "task": "kill process on port",
        "ok": r"\b(kill|fuser|lsof|pkill|ss)\b",
        "p": {
            "en": "kill the process using port 8080",
            "rojak": "nak kill process guna port 8080",
            "collo": "nak matikan process yang guna port 8080",
            "formal": "Hentikan process yang menggunakan port 8080",
        },
    },
    {
        "task": "open firewall port",
        "ok": r"\b(ufw|firewall-cmd|iptables|nft)\b",
        "p": {
            "en": "open firewall port 22",
            "rojak": "nak open firewall port 22",
            "collo": "nak buka port 22 kat firewall",
            "formal": "Buka port 22 pada firewall",
        },
    },
    {
        "task": "change permission",
        "ok": r"\b(chmod|chown|setfacl)\b",
        "p": {
            "en": "make a file executable",
            "rojak": "nak tukar permission file ni",
            "collo-fail": "nak tukar permission fail ni",
            "collo-keizinan": "nak ubah keizinan file ni",
            "formal": "Tukar permission file tersebut",
        },
    },
    {
        "task": "create user",
        "ok": r"\b(useradd|adduser)\b",
        "p": {
            "en": "create a new user",
            "rojak": "nak create user baru",
            "collo": "nak buat user baru",
            "collo-pengguna": "nak buat pengguna baru",
            "formal": "Buat satu user baharu",
        },
    },
    {
        "task": "compress folder",
        "ok": r"\b(tar|zip|gzip|7z|xz)\b",
        "p": {
            "en": "compress this folder",
            "rojak": "nak compress folder ni",
            "collo-mampat": "nak mampatkan folder ni",
            "formal": "Mampatkan folder ini",
        },
    },
    {
        "task": "search text in files",
        "ok": r"\b(grep|rg|ag|ack|find)\b",
        "p": {
            "en": "search for 'error' in all files",
            "rojak": "nak search 'error' dalam semua file",
            "collo-cari": "nak cari 'error' dalam semua file",
            "collo-fail": "nak cari 'error' dalam semua fail",
            "formal": "Cari perkataan 'error' dalam semua file",
        },
    },
    {
        "task": "download a url",
        "ok": r"\b(curl|wget|aria2c|http)\b",
        "p": {
            "en": "download https://example.com/a.txt",
            "rojak": "nak download https://example.com/a.txt",
            "collo-muat": "nak muat turun https://example.com/a.txt",
            "formal": "Muat turun https://example.com/a.txt",
        },
    },
    # --- added with dataset/basics.txt (issue #41). Every phrasing below is
    # absent from basics.txt verbatim (checked at startup), so this scores
    # generalisation across phrasing, not recall of training rows.
    {
        "task": "read file",
        "ok": r"\b(cat|less|more|head|tail|bat|vim|nano|view)\b",
        "p": {
            "en": "show me what is in readme.txt",
            "rojak": "nak tengok isi file readme.txt",
            "collo-baca": "nak baca readme.txt",
            "collo-fail": "tunjuk isi fail readme.txt",
            "formal": "Paparkan kandungan fail readme.txt",
            "short-tgk": "tgk isi readme.txt",
        },
    },
    {
        "task": "find file by name",
        "ok": r"\b(find|locate|fd|ls|mdfind)\b",
        "p": {
            "en": "where did I put invoice.pdf",
            "rojak": "nak search invoice.pdf kat mana",
            "collo-cari": "cari fail invoice.pdf",
            "collo-mana": "mana fail invoice.pdf aku",
            "formal": "Cari fail bernama invoice.pdf",
            "short-dlm": "cari invoice.pdf dlm folder ni",
        },
    },
    {
        "task": "where am i",
        "ok": r"\bpwd\b|\$PWD",
        "p": {
            "en": "which folder am I in right now",
            "rojak": "sekarang aku kat directory mana",
            "collo": "aku kat mana ni",
            "formal": "Paparkan laluan direktori semasa",
            "short-skrg": "skrg aku kat folder mana",
        },
    },
    {
        "task": "my ip",
        "ok": r"\b(ip|ifconfig|hostname|curl|wget|dig)\b",
        "p": {
            "en": "show me my ip",
            "rojak": "nak tahu IP address laptop ni",
            "collo": "IP aku berapa eh",
            "formal": "Tunjukkan alamat IP mesin ini",
            "short-sy": "sy nak tahu ip sy",
        },
    },
    {
        "task": "edit file",
        "ok": r"\b(nano|vim|vi|micro|code|gedit|emacs)\b",
        "p": {
            "en": "open readme.txt so I can edit it",
            "rojak": "nak edit readme.txt",
            "collo-ubah": "nak ubah isi fail readme.txt",
            "collo-edit": "buka readme.txt nak edit sikit",
            "formal": "Sunting fail readme.txt",
        },
    },
    {
        "task": "exit vim",
        "ok": r":q|:wq|:x\b|ZZ",
        "p": {
            "en": "how do I get out of vim",
            "rojak": "camne nak exit vim ni",
            "collo": "nak keluar vim tapi tak boleh",
            "formal": "Keluar daripada editor vim",
            "short-x": "x boleh keluar vim, macam mana",
        },
    },
    {
        "task": "exit nano",
        "ok": r"Ctrl.?x|\^X",
        "p": {
            "en": "how to close nano",
            "rojak": "nak keluar dari nano macam mana",
            "collo": "nak tutup nano ni, tekan apa",
            "formal": "Tutup editor nano",
        },
    },
    {
        "task": "extract archive",
        "ok": r"\b(tar|unzip|7z|unrar|gunzip|bsdtar)\b",
        "p": {
            "en": "unpack data.tar.gz",
            "rojak": "nak extract data.tar.gz ni",
            "collo-buka": "nak buka fail data.tar.gz",
            "collo-nyah": "nyahmampat data.tar.gz",
            "formal": "Ekstrak arkib data.tar.gz",
            "short-tlg": "tlg extract data.tar.gz",
        },
    },
    {
        "task": "move file",
        "ok": r"\b(mv|rsync)\b",
        "p": {
            "en": "put report.pdf into the Documents folder",
            "rojak": "nak move report.pdf masuk Documents",
            "collo-pindah": "pindahkan report.pdf ke Documents",
            "collo-alih": "alihkan fail report.pdf masuk folder Documents",
            "formal": "Pindahkan fail report.pdf ke direktori Documents",
            "short-msk": "nak pindah report.pdf msk Documents",
        },
    },
    {
        "task": "count lines",
        "ok": r"\b(wc|awk|grep -c|sed -n)\b",
        "p": {
            "en": "how many lines are in data.csv",
            "rojak": "nak count line dalam data.csv",
            "collo-kira": "kira baris dalam fail data.csv",
            "collo-berapa": "berapa baris ada dalam data.csv",
            "formal": "Kira bilangan baris dalam fail data.csv",
        },
    },
    {
        "task": "check internet",
        "ok": r"\b(ping|curl|wget|nc|traceroute|nmcli)\b",
        "p": {
            "en": "is my internet working",
            "rojak": "nak check internet connect ke tak",
            "collo": "internet ni jalan ke tak",
            "formal": "Uji sambungan internet",
            "short-x": "internet x jalan ke, camne nak check",
        },
    },
    {
        "task": "git commit",
        "ok": r"\bgit\s+commit\b",
        "p": {
            "en": "commit my changes with the message add login",
            "rojak": "nak commit dengan message add login",
            "collo": "commit perubahan aku, mesej dia add login",
            "formal": "Buat commit dengan mesej add login",
        },
    },
    {
        "task": "install package",
        "ok": r"\b(apt|apt-get|dnf|yum|pacman|brew|zypper|snap|apk)\b",
        "p": {
            "en": "install htop on my machine",
            "rojak": "nak install htop",
            "collo-pasang": "pasang htop",
            "collo-mcm": "mcm mana nak pasang htop",
            "formal": "Pasang perisian htop",
        },
    },
    {
        "task": "run script",
        "ok": r"(^|\s|/)(bash|sh|\./)\S*|chmod",
        "p": {
            "en": "run the script deploy.sh",
            "rojak": "nak run deploy.sh",
            "collo": "jalankan deploy.sh",
            "formal": "Laksanakan skrip deploy.sh",
            "short-mcm": "mcm mana nak run deploy.sh ni",
        },
    },
    {
        "task": "follow log",
        "ok": r"\b(tail|less|journalctl|multitail)\b",
        "p": {
            "en": "keep showing new lines of server.log",
            "rojak": "nak tengok server.log live",
            "collo": "tunjuk server.log yang tengah jalan, update terus",
            "formal": "Ikuti fail server.log secara langsung",
        },
    },
    {
        "task": "ram usage",
        "ok": r"\b(free|top|htop|vmstat|cat /proc/meminfo)\b",
        "p": {
            "en": "how much memory is in use",
            "rojak": "nak check RAM tinggal berapa",
            "collo": "RAM laptop ni tinggal berapa",
            "formal": "Paparkan penggunaan memori",
            "short-tgk": "tgk ram usage skrg",
        },
    },
    {
        "task": "ssh into server",
        "ok": r"\bssh\b",
        "p": {
            "en": "log in to 10.0.0.5 as ariff",
            "rojak": "nak masuk server 10.0.0.5 as ariff",
            "collo": "nak connect ke server 10.0.0.5 guna user ariff",
            "formal": "Sambung ke pelayan 10.0.0.5 sebagai ariff",
        },
    },
    {
        "task": "history",
        "ok": r"\b(history|fc)\b",
        "p": {
            "en": "what commands did I run today",
            "rojak": "nak tengok command yang aku dah type",
            "collo": "apa yang aku taip tadi",
            "formal": "Paparkan sejarah arahan",
        },
    },
    {
        "task": "empty folder delete",
        "ok": r"\b(rmdir|rm)\b",
        "p": {
            "en": "remove the empty folder temp",
            "rojak": "nak delete folder temp yang kosong tu",
            "collo": "buang folder temp, dia kosong je",
            "formal": "Padam direktori kosong temp",
        },
    },
    {
        "task": "copy folder",
        "ok": r"\b(cp|rsync)\b",
        "p": {
            "en": "duplicate the folder website as website_old",
            "rojak": "nak copy folder website jadi website_old",
            "collo-salin": "salin folder website ke website_old",
            "collo-fail": "buat salinan folder website nama website_old",
            "formal": "Salin direktori website kepada website_old",
        },
    },
]

# Tasks deliberately ABSENT from dataset/basics.txt: the tools below do not
# appear there at all. If these move with a basics-trained model, the gain
# generalised past the rows we wrote; if only the block above moves, it did
# not. Adding any of these tools to basics.txt retires it from this list.
HOLDOUT = [
    {
        "task": "holdout: empty a file",
        "ok": r"\btruncate\b|(^|\s|:)>\s*\S|cp /dev/null|echo -n",
        "p": {
            "en": "empty the file app.log without deleting it",
            "rojak": "nak kosongkan file app.log tapi jangan delete",
            "collo": "kosongkan isi app.log, fail tu jangan buang",
            "formal": "Kosongkan kandungan fail app.log tanpa memadamnya",
        },
    },
    {
        "task": "holdout: reverse lines",
        "ok": r"\b(tac|sed|awk|perl|sort -r)\b",
        "p": {
            "en": "print notes.txt with the last line first",
            "rojak": "nak print notes.txt reverse order",
            "collo": "tunjuk notes.txt dari baris bawah ke atas",
            "formal": "Paparkan notes.txt dalam susunan baris terbalik",
        },
    },
    {
        "task": "holdout: whereis",
        "ok": r"\b(whereis|which|type|command -v|locate)\b",
        "p": {
            "en": "find where git and its man page are installed",
            "rojak": "nak tahu binary git kat mana",
            "collo": "git ni install kat mana",
            "formal": "Cari lokasi binari dan manual git",
        },
    },
    {
        "task": "holdout: dirname",
        "ok": r"\b(dirname|sed|awk|\$\{.*%)",
        "p": {
            "en": "get just the folder part of /home/ariff/docs/a.txt",
            "rojak": "nak folder path je dari /home/ariff/docs/a.txt",
            "collo": "ambil nama folder je dari /home/ariff/docs/a.txt",
            "formal": "Ambil laluan direktori daripada /home/ariff/docs/a.txt",
        },
    },
    {
        "task": "holdout: tee",
        "ok": r"\btee\b",
        "p": {
            "en": "show the output of ls and also save it to list.txt",
            "rojak": "nak tengok output ls and save ke list.txt sekali",
            "collo": "tunjuk output ls kat skrin, simpan dalam list.txt sekali",
            "formal": "Paparkan output ls dan simpan ke list.txt serentak",
        },
    },
    {
        "task": "holdout: timeout",
        "ok": r"\b(timeout|ulimit -t)\b",
        "p": {
            "en": "run ./slow.sh but stop it after 10 seconds",
            "rojak": "nak run ./slow.sh tapi kill lepas 10 saat",
            "collo": "jalankan ./slow.sh, kalau lebih 10 saat matikan",
            "formal": "Jalankan ./slow.sh dengan had masa 10 saat",
        },
    },
    {
        "task": "holdout: change shell",
        "ok": r"\b(chsh|usermod -s)\b",
        "p": {
            "en": "make zsh my default shell",
            "rojak": "nak tukar default shell ke zsh",
            "collo": "tukar shell aku jadi zsh",
            "formal": "Tetapkan zsh sebagai shell lalai",
        },
    },
    {
        "task": "holdout: printenv",
        "ok": r"\b(printenv|env)\b|echo \W*\$\{?HOME",
        "p": {
            "en": "print the value of the HOME variable",
            "rojak": "nak print value env HOME",
            "collo": "tunjuk nilai variable HOME",
            "formal": "Paparkan nilai pemboleh ubah HOME",
        },
    },
    {
        "task": "holdout: number lines",
        "ok": r"\b(nl|cat -n|awk|sed =|grep -n)\b",
        "p": {
            "en": "print notes.txt with a number in front of every line",
            "rojak": "nak print notes.txt dengan nombor kat setiap line",
            "collo": "tunjuk notes.txt, letak nombor depan setiap baris",
            "formal": "Paparkan notes.txt dengan nombor baris",
        },
    },
    {
        "task": "holdout: five biggest files",
        "ok": r"\b(du|ls|find)\b.*\b(sort|head)\b|\bls -\w*S",
        "p": {
            "en": "show the five biggest files in this folder",
            "rojak": "nak tengok 5 file paling besar kat sini",
            "collo": "fail mana 5 yang paling besar dalam folder ni",
            "formal": "Senaraikan lima fail terbesar dalam direktori ini",
        },
    },
]

# The homograph guard: `fail` is *file* in Malay and *failure* in English.
# A fix that teaches the Malay sense must not eat the English one.
HOMOGRAPH = [
    ("bm-sense", "nak buat fail baru", r"\b(touch|tee|>\s*\S|printf)"),
    ("bm-sense", "nak buang fail lama", r"\b(rm|unlink|find)\b"),
    ("bm-sense", "nak cari fail besar", r"\b(find|du|ls)\b"),
    ("en-sense", "exit the shell when a command fails", r"set\s+-e|\|\||exit"),
    ("en-sense", "retry the command if it fails", r"until|while|retry|\|\|"),
    ("en-sense", "show only lines where the test failed", r"\b(grep|awk|sed)\b"),
]


def chatml(q):
    return (f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
            f"<|im_start|>user\n{q}<|im_end|>\n<|im_start|>assistant\n")


def ask(q):
    body = json.dumps({"prompt": chatml(q), "n_predict": 64, "temperature": 0,
                       "grammar": "root ::= [ -~]+", "stop": ["\n"],
                       "repeat_penalty": 1.08, "repeat_last_n": 64,
                       "cache_prompt": True}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/completion", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["content"].strip()


def boot(server, model, threads):
    p = subprocess.Popen([server, "-m", model, "-t", str(threads), "-c", "2048",
                          "-ngl", "0", "--no-webui", "--port", str(PORT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.monotonic()
    while True:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            return p
        except Exception:
            if time.monotonic() - t0 > 300:
                p.kill()
                raise RuntimeError("server never became ready")
            time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--server", default=PINNED if os.path.exists(PINNED) else "llama-server")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", default="out/probe.jsonl")
    ap.add_argument("--rescore", metavar="JSONL",
                    help="re-apply the current regexes to a saved run; no server")
    args = ap.parse_args()

    # The probe must not score its own training data. dataset/basics.txt is
    # hand-written and lives next door, so check every prompt against it.
    basics_txt = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "dataset", "basics.txt")
    if os.path.exists(basics_txt):
        import sys
        sys.path.insert(0, os.path.dirname(basics_txt))
        from basics import parse as parse_basics
        train = {p.lower() for _, regs in parse_basics(basics_txt)
                 for ps in regs.values() for p in ps}
        leaked = [p for t in TASKS + HOLDOUT for p in t["p"].values()
                  if p.lower() in train]
        if leaked:
            raise SystemExit(f"probe prompts present in basics.txt: {leaked}")

    if args.rescore:
        okre = {t["task"]: t["ok"] for t in TASKS + HOLDOUT}
        okre.update({("homograph", p): r for _, p, r in HOMOGRAPH})
        rows = [json.loads(l) for l in open(args.rescore, encoding="utf-8")]
        for r in rows:
            pat = okre[("homograph", r["prompt"])] if r["task"] == "homograph" else okre[r["task"]]
            r["ok"] = bool(re.search(pat, r["got"]))
        report(rows)
        return

    proc = boot(args.server, args.model, args.threads)
    rows = []
    try:
        for t in TASKS:
            for axis, prompt in t["p"].items():
                got = ask(prompt)
                rows.append({"task": t["task"], "axis": axis, "prompt": prompt,
                             "got": got, "ok": bool(re.search(t["ok"], got))})
        for t in HOLDOUT:
            for axis, prompt in t["p"].items():
                got = ask(prompt)
                rows.append({"task": t["task"], "axis": axis, "prompt": prompt,
                             "got": got, "ok": bool(re.search(t["ok"], got))})
        for axis, prompt, ok_re in HOMOGRAPH:
            got = ask(prompt)
            rows.append({"task": "homograph", "axis": axis, "prompt": prompt,
                         "got": got, "ok": bool(re.search(ok_re, got))})
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=30)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report(rows)


def report(rows):
    # group axes into the families we actually want to compare
    def family(axis):
        if axis.startswith("count"):
            return "count"
        if axis.startswith("short"):
            return "shortcut"
        if axis in ("en", "rojak", "formal") or axis.startswith("collo"):
            for key in ("fail", "direktori", "pengguna", "cakera", "keizinan",
                        "mampat", "muat", "salin", "padam", "senarai", "cari",
                        "tukar", "buang", "tunjuk", "tengok", "cipta"):
                if axis.endswith(key):
                    return "bm-vocab" if key in (
                        "fail", "direktori", "pengguna", "cakera", "keizinan",
                        "mampat", "muat") else "bm-verb"
            return {"en": "english", "rojak": "rojak",
                    "formal": "formal"}.get(axis, "colloquial")
        return axis

    print(f"\n{len(rows)} prompts, tool-level scoring\n")
    fam = {}
    for r in rows:
        if r["task"] == "homograph" or r["task"].startswith("holdout"):
            continue
        f_ = family(r["axis"])
        fam.setdefault(f_, []).append(r["ok"])
    print(f"{'family':12s} {'pass':>8s}  n")
    for f_, v in sorted(fam.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        print(f"{f_:12s} {sum(v)/len(v):8.2f}  {len(v)}")

    ho = [r["ok"] for r in rows if r["task"].startswith("holdout")]
    seen = [r["ok"] for r in rows
            if r["task"] != "homograph" and not r["task"].startswith("holdout")]
    print(f"\n{'basics tasks':12s} {sum(seen)/len(seen):8.2f}  {len(seen)}   (tasks in basics.txt, phrasings not)")
    print(f"{'holdout':12s} {sum(ho)/len(ho):8.2f}  {len(ho)}   (tools absent from basics.txt)")

    hom = {}
    for r in rows:
        if r["task"] == "homograph":
            hom.setdefault(r["axis"], []).append(r["ok"])
    print(f"\nhomograph guard")
    for a, v in sorted(hom.items()):
        print(f"{a:12s} {sum(v)/len(v):8.2f}  {len(v)}")

    print("\nfailures:")
    for r in rows:
        if not r["ok"]:
            print(f"  [{r['task']}/{r['axis']}] {r['prompt']}\n      => {r['got']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fix the tool-frequency inversion. Stdlib only.

  python3 rebalance.py out/pool_v3.aug.jsonl out/pool_v3.bal.jsonl

The pool ships 6,785 distinct tools and `shuf` outweighed `touch` 11 to 1.
When a prompt lands off-distribution the model picks from that long tail, so
"compress this folder" came back `zoxide add` and "delete this file" came back
`git obliterate`.

Three knobs, and no fourth:

  --floor N   drop tools with fewer than N rows. A tool seen twice cannot be
              learned; all it teaches is that the token exists, which is
              exactly the failure. Cheap: the whole tail below 8 is 2.4% of
              rows and 29% of the tool vocabulary.

  --cap N     ceiling for non-core tools only. `shuf` had 5,387 rows against
              `touch`'s 469. `find` has 58,299 and keeps them: it is core and
              genuinely is the answer that often, which is why the cap is not
              applied across the board.

  --core M    duplicate rows of the beginner tools until each has M. Raising
              the common tools rather than deleting the rare ones is
              deliberate — RESULTS.md shows English accuracy tracking pool
              size monotonically, so a big prune buys the tool balance and
              pays for it in accuracy, which is the mistake run 2 made.

Commands are never rewritten, so byte-identity holds.

ponytail: duplication is a blunt reweight. With one epoch and four registers
already giving four views per command it is acceptable, and probe.py plus the
ALFA run are what would catch it turning into memorisation. If it ever does,
the upgrade is per-row sample weights in the trainer, not a smarter script.
"""
import argparse
import json
from collections import Counter

# Tools someone who has never used a terminal actually needs. Keep this list
# about the beginner, not about coverage — breadth is what the tail was for.
CORE = """
ls cd pwd cat less head tail touch mkdir rmdir rm cp mv ln find grep wc sort
uniq cut tr sed awk tee xargs echo printf chmod chown stat file du df mount
umount lsblk ps top kill pkill pgrep jobs bg fg nohup systemctl service
journalctl uname hostname whoami who id uptime free date cal history man
which whereis tar gzip gunzip zip unzip curl wget ssh scp rsync ping ip
ifconfig netstat ss traceroute nslookup dig ufw iptables apt dnf yum pacman
brew pip npm git docker nano vim code diff comm tree alias export env sleep
watch clear exit sudo su passwd useradd userdel usermod groupadd crontab at
mktemp basename dirname realpath readlink seq yes true false test
""".split()


def tool(cmd, skip=frozenset(
        {"sudo", "env", "time", "nohup", "doas", "command", "exec"})):
    for t in cmd.split():
        if t in skip:
            continue
        return t.split("/")[-1]
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--floor", type=int, default=8)
    ap.add_argument("--core", type=int, default=1500)
    ap.add_argument("--cap", type=int, default=1200,
                    help="ceiling for non-core tools")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.src, encoding="utf-8")]
    for r in rows:
        r["_t"] = tool(r["cmd"])
    count = Counter(r["_t"] for r in rows)

    kept, seen = [], Counter()
    core = set(CORE)
    for r in rows:
        if count[r["_t"]] < args.floor:
            continue
        # Ceiling applies to non-core only: `shuf` had 5,387 rows against
        # `touch`'s 469, while `find` is legitimately the answer to a lot and
        # is core, so a blanket cap would cut the wrong tool.
        if r["_t"] not in core and seen[r["_t"]] >= args.cap:
            continue
        seen[r["_t"]] += 1
        kept.append(r)
    dropped_tools = sum(1 for t, n in count.items() if n < args.floor)

    by_tool = {}
    for r in kept:
        by_tool.setdefault(r["_t"], []).append(r)

    extra = []
    for t in CORE:
        have = by_tool.get(t)
        if not have:
            continue
        need = args.core - len(have)
        i = 0
        while need > 0:                    # cycle in file order, reproducible
            src = have[i % len(have)]
            extra.append({**src, "id": f"{src['id']}~{i}"})
            i += 1
            need -= 1

    out = kept + extra
    after = Counter(r["_t"] for r in out)
    print(f"in {len(rows)}  dropped {len(rows)-len(kept)} rows / "
          f"{dropped_tools} tools below floor {args.floor}")
    print(f"upsampled {len(extra)} rows into {sum(1 for t in CORE if t in by_tool)} "
          f"core tools -> {len(out)} rows, {len(after)} tools")
    core_rows = sum(after[t] for t in CORE)
    print(f"core share {100*core_rows/len(out):.1f}% (was "
          f"{100*sum(count[t] for t in CORE)/len(rows):.1f}%)")
    for t in ("touch", "mkdir", "cp", "rm", "tar", "shuf", "zoxide", "pm2"):
        print(f"  {t:10s} {count.get(t,0):>7} -> {after.get(t,0):>7}")
    if args.dry_run:
        return
    with open(args.dst, "w", encoding="utf-8") as f:
        for r in out:
            r.pop("_t", None)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} rows -> {args.dst}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Last pass before training: drop untrainable rows and disambiguate prompts
that map to many different commands. Stdlib only.

  python3 disambiguate.py out/pool.jsonl out/pool.train.jsonl

Two defects this fixes, both from tldr's page structure:

1. Junk targets. Pages for interactive TUIs list keybindings, not commands:
   "Scroll down" -> `<Spacebar>`. Not shell, never useful, dropped.

2. Generic descriptions. Every tldr page has "Display help", so one prompt
   maps to ~880 different commands. Training on that teaches the model to
   guess a random tool name for a common phrase — and "display help" is the
   single most frequent prompt in the pool, so the damage is concentrated
   exactly where it hurts. Real users name the tool ("camne nak tengok help
   docker"), so the tool name belongs in the prompt for these rows.

   Only colliding prompts get the tool appended. Prompts that already
   identify their command ("cari file lagi besar dari 100MB") are left alone
   — adding the tool there would teach the model to expect a name real
   queries do not carry.

Whole pairs are dropped or rewritten, never single registers, so all four
stay in sync. Commands are never modified; verify.py still passes after.
"""
import collections
import json
import re
import sys

# `<Spacebar>`, `q`, `:wq`, `Ctrl + C` — tldr keybinding rows, not commands.
JUNK = re.compile(r"^\s*(<[^>]+>|[A-Za-z]|:\w+|Ctrl\s*\+.*|Alt\s*\+.*)\s*$")

# Prefixes that are not the tool being described.
SKIP = {"sudo", "env", "time", "nohup", "doas", "command", "exec"}

# Register-appropriate way to name the tool. Technical noun, stays English.
JOIN = {
    "formal": " untuk {}",
    "colloquial": " {}",
    "rojak": " {}",
    "english": " for {}",
}


def tool_of(cmd):
    """The command's tool name, as a user would say it."""
    for tok in cmd.split():
        if tok in SKIP or "=" in tok:
            continue
        tok = tok.lstrip("./")
        return tok if re.match(r"^[\w.+-]+$", tok) else ""
    return ""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]

    by_id = collections.defaultdict(list)
    for r in rows:
        by_id[r["id"]].append(r)

    dropped_junk = [i for i, rs in by_id.items() if JUNK.match(rs[0]["cmd"])]
    for i in dropped_junk:
        del by_id[i]

    # Group pairs by their English (source) description: same description,
    # different commands means the prompt cannot identify its answer.
    groups = collections.defaultdict(list)
    for i, rs in by_id.items():
        eng = next((r["nl"] for r in rs if r["register"] == "english"), "")
        groups[eng.lower()].append(i)

    disambiguated = dropped_dup = 0
    for eng, ids in groups.items():
        cmds = {by_id[i][0]["cmd"] for i in ids}
        if len(cmds) < 2:
            continue
        # Name the tool in every register of every pair in the group.
        for i in ids:
            tool = tool_of(by_id[i][0]["cmd"])
            if not tool:
                continue
            for r in by_id[i]:
                if re.search(r"\b" + re.escape(tool) + r"\b", r["nl"], re.I):
                    continue  # prompt already names it
                r["nl"] += JOIN[r["register"]].format(tool)
            disambiguated += 1
        # Same description AND same tool, different commands (flag variants):
        # keep the shortest, which is the canonical form.
        per_tool = collections.defaultdict(list)
        for i in ids:
            per_tool[tool_of(by_id[i][0]["cmd"])].append(i)
        for tool, tids in per_tool.items():
            if len(tids) < 2:
                continue
            keep = min(tids, key=lambda i: (len(by_id[i][0]["cmd"]), by_id[i][0]["cmd"]))
            for i in tids:
                if i != keep:
                    del by_id[i]
                    dropped_dup += 1

    out = [r for i in by_id for r in by_id[i]]
    with open(dst, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"dropped {len(dropped_junk)} junk pairs (keybindings, not commands)")
    print(f"named the tool in {disambiguated} ambiguous pairs")
    print(f"dropped {dropped_dup} same-prompt-same-tool duplicate pairs")
    print(f"{len(out)} rows ({len(by_id)} pairs) -> {dst}")


if __name__ == "__main__":
    main()

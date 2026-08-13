#!/usr/bin/env python3
"""Extract (nl, command) pairs from tldr-pages into raw/tldr.csv — same
columns as nl2sh_train.csv, so registers.py/stoplist.py/verify.py run on it
unchanged. Stdlib only.

tldr content is CC-BY-4.0: NOTICE at the repo root carries the attribution.

  python3 tldr.py            # downloads the main tarball on first run

Page format, one pair per example:

  - Create specific files:

  `touch {{path/to/file1}}`

ponytail: pages/common + pages/linux only — osx is mostly BSD-flag variants
of the same tools and windows is powershell; add per-platform sets when a
platform-aware dataset field exists.
"""
import csv
import io
import os
import re
import tarfile
import urllib.request

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
TARBALL = "https://github.com/tldr-pages/tldr/archive/refs/heads/main.tar.gz"
PLATFORMS = ("pages/common/", "pages/linux/")


def parse_page(text, name):
    """One (nl, cmd) per example.

    ponytail: descriptions are kept verbatim, so generic ones ('Start the
    daemon:') map to many tools across pages. That is prior-teaching noise,
    accepted; appending the tool name instead leaks the answer into the
    prompt and trains a shortcut real queries never provide.
    """
    pairs = []
    desc = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- ") and line.endswith(":"):
            desc = line[2:-1].strip()
        elif line.startswith("`") and line.endswith("`") and desc:
            cmd = line[1:-1].replace("{{", "").replace("}}", "")
            pairs.append((desc, cmd))
            desc = None
    return pairs


def main():
    os.makedirs(RAW, exist_ok=True)
    tar_path = os.path.join(RAW, "tldr-main.tar.gz")
    if not os.path.exists(tar_path):
        print("downloading tldr-pages tarball...")
        urllib.request.urlretrieve(TARBALL, tar_path)

    rows = []
    with tarfile.open(tar_path) as tar:
        for member in tar.getmembers():
            parts = member.name.split("/", 1)
            if len(parts) < 2 or not member.name.endswith(".md"):
                continue
            rel = parts[1]
            if not rel.startswith(PLATFORMS):
                continue
            name = os.path.basename(rel)[:-3]
            text = tar.extractfile(member).read().decode("utf-8")
            rows.extend(parse_page(text, name))

    out = os.path.join(RAW, "tldr.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nl", "bash"])
        w.writerows(rows)
    print(f"{len(rows)} pairs -> {out}")


if __name__ == "__main__":
    main()

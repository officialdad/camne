# camne demo — re-record with:  vhs demo/demo.tape   (from the repo root)
#
# Needs: vhs, ttyd, ffmpeg, Go. The tape builds camne from source itself.
# Scenes 1-3 use the model already in ~/.cache/camne (check with
# `camne doctor`). Scene 3 deletes that model's .sha256 sidecar to stage the
# first run after an update — camne re-checks the model it already has and
# writes the sidecar straight back, so the cache ends the way it started.
# Scene 4 runs `camne doctor` against an empty cache: it reports what is
# missing and touches nothing, so this tape never downloads anything. Do NOT
# put a bare query in scene 4 — since the consent prompt was dropped, a query
# on an empty cache downloads ~1 GB.
#
# vhs records through a pty, so camne sees a terminal and colours its output.
#
# Malay in, English out. The typed queries stay Malay — that is the product,
# not a translation gap — while everything camne prints back is English.

Output demo/demo.gif

Set Shell bash
Set FontSize 19
Set Width 1200
Set Height 320
Set Padding 24
Set TypingSpeed 55ms
Set Framerate 20

# Setup (not recorded): build the binary, clean prompt, and run one throwaway
# query so the model is checked, its sidecar written, and llama-server resident
# before scene 1 — none of which is what scenes 1 and 2 are about.
Hide
Type `export PS1="$ " PROMPT_COMMAND= ; mkdir -p /tmp/camne-demo && go build -o /tmp/camne-demo/camne ./cmd/camne && export PATH=/tmp/camne-demo:$PATH && camne nak list file > /dev/null 2>&1 && clear`
Enter
Sleep 60s
Show

# 1. Colloquial Malay question, English command comes back.
Type "camne nak cari file besar dari 100MB dalam home"
Sleep 500ms
Enter
Sleep 3s

# 2. A flagged command gets a magenta `camne warning:` line per reason, above
#    the command and closed by a blank line. camne still runs nothing.
Type "camne nak delete semua file dalam /etc"
Sleep 500ms
Enter
Sleep 4s

# 3. The first run after an update: the wordmark, then camne checking the model
#    it already has against the digest this version expects. No download.
Hide
Type `rm -f "${XDG_CACHE_HOME:-$HOME/.cache}"/camne/models/*.sha256 && clear`
Enter
Sleep 1s
Show
Type "camne nak kira berapa banyak file dalam folder ni"
Sleep 500ms
Enter
Sleep 6s

# 4. A fresh machine: `camne doctor` shows what camne will fetch on first run.
Hide
Type `export XDG_CACHE_HOME=/tmp/camne-fresh && rm -rf /tmp/camne-fresh && clear`
Enter
Sleep 2s
Show
Type "camne doctor"
Sleep 500ms
Enter
Sleep 4s

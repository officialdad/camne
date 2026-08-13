# camne demo — re-record with:  vhs demo/demo.tape   (from the repo root)
#
# Needs: vhs, ttyd, ffmpeg, Go. The tape builds camne from source itself.
# Scenes 1 and 2 use the model already in ~/.cache/camne (check with
# `camne doctor`). Scene 3 runs `camne doctor` against an empty cache: it
# reports what is missing and touches nothing, so this tape never downloads
# anything. Do NOT put a bare query here — since the consent prompt was
# dropped, a query on an empty cache downloads ~1 GB.
#
# The typed queries stay in Malay: that is the product, not a translation gap.

Output demo/demo.gif

Set Shell bash
Set FontSize 19
Set Width 1000
Set Height 320
Set Padding 24
Set TypingSpeed 55ms
Set Framerate 20

# Setup (not recorded): build the binary, clean prompt.
Hide
Type `export PS1="$ " PROMPT_COMMAND= ; mkdir -p /tmp/camne-demo && go build -o /tmp/camne-demo/camne ./cmd/camne && export PATH=/tmp/camne-demo:$PATH && clear`
Enter
Sleep 30s
Show

# 1. Colloquial Malay question, command comes back.
Type "camne nak buat file baru"
Sleep 500ms
Enter
Sleep 3s

# 2. A dangerous command gets the BAHAYA banner. camne still runs nothing.
Type "camne nak delete semua file dalam /etc"
Sleep 500ms
Enter
Sleep 4s

# 3. A fresh machine: `camne doctor` shows what camne will fetch on first run.
Hide
Type `export XDG_CACHE_HOME=$(mktemp -d) && clear`
Enter
Sleep 2s
Show
Type "camne doctor"
Sleep 500ms
Enter
Sleep 4s

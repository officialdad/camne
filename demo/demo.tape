# camne demo — re-record with:  vhs demo/demo.tape   (dari root repo)
#
# Perlu: vhs, ttyd, ffmpeg, Go. Tape ni build camne dari source sendiri.
# Scene 1 dan 2 guna model yang dah ada dalam ~/.cache/camne (semak dengan
# `camne doctor`). Scene 3 tunjuk skrin kali-pertama guna cache kosong dan
# JAWAB TIDAK — jadi tape ni tak pernah download apa-apa.

Output demo/demo.gif

Set Shell bash
Set FontSize 19
Set Width 1000
Set Height 320
Set Padding 24
Set TypingSpeed 55ms
Set Framerate 20

# Setup (tak dirakam): build binary, prompt bersih.
Hide
Type `export PS1="$ " PROMPT_COMMAND= ; mkdir -p /tmp/camne-demo && go build -o /tmp/camne-demo/camne ./cmd/camne && export PATH=/tmp/camne-demo:$PATH && clear`
Enter
Sleep 30s
Show

# 1. Soalan BM colloquial, dapat command.
Type "camne nak buat file baru"
Sleep 500ms
Enter
Sleep 3s

# 2. Command bahaya dapat banner BAHAYA. camne tetap tak jalankan apa-apa.
Type "camne nak delete semua file dalam /etc"
Sleep 500ms
Enter
Sleep 4s

# 3. Kali pertama pada mesin baru: camne tanya kebenaran sebelum download.
Hide
Type `export XDG_CACHE_HOME=$(mktemp -d) && clear`
Enter
Sleep 2s
Show
Type "camne macam mana nak zip folder ni"
Sleep 500ms
Enter
Sleep 3s
Type "t"
Sleep 800ms
Enter
Sleep 3s

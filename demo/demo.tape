# camne demo — re-record with:  vhs demo/demo.tape   (from the repo root)
#
# Needs: vhs, ttyd, ffmpeg, Go. The tape builds camne from source itself.
# Every scene uses the model already in ~/.cache/camne (check with
# `camne doctor`); the tape never downloads anything.
#
# vhs records through a pty, so camne sees a terminal and colours its output.
#
# Malay in, English out. The typed queries stay Malay — that is the product,
# not a translation gap — while everything camne prints back is English.

Output demo/demo.gif

Set Shell bash
Set FontSize 19
Set Width 1200
Set Height 420
Set Padding 24
Set TypingSpeed 55ms
Set Framerate 20

# Setup (not recorded): build the binary, clean prompt, and run one throwaway
# query so llama-server is resident before scene 1.
Hide
Type `export PS1="$ " PROMPT_COMMAND= ; mkdir -p /tmp/camne-demo && go build -o /tmp/camne-demo/camne ./cmd/camne && export PATH=/tmp/camne-demo:$PATH && camne nak list file > /dev/null 2>&1 && clear`
Enter
Sleep 60s
Show

# The first five things a beginner asks, in the Malay they would actually type.
Type "camne nak exit vim"
Sleep 500ms
Enter
Sleep 2500ms

Type "camne nak tengok fail hidden"
Sleep 500ms
Enter
Sleep 2500ms

Type "camne nak list port bukak"
Sleep 500ms
Enter
Sleep 2500ms

# Say which system: the install command depends on it. Needs root, so a
# magenta `camne warning:` line sits above the command. Nothing runs.
Type "camne nak install btop untuk arch"
Sleep 500ms
Enter
Sleep 3s

Type "camne nak reset password"
Sleep 500ms
Enter
Sleep 4s

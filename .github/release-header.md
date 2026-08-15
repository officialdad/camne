Six static binaries — Linux, macOS and Windows on both amd64 and arm64. No runtime, no dependencies, nothing to install alongside them.

**Linux / macOS:** `curl -fsSL https://raw.githubusercontent.com/officialdad/camne/main/install.sh | sh`
**Windows:** download `camne_windows_amd64.exe` (or `camne_windows_arm64.exe`) below.

Every asset's SHA-256 is in `checksums.txt`. `install.sh` verifies it before installing and refuses on a mismatch.

On first run camne downloads llama-server and the model (~1 GB, once), printing the size before it starts and the progress while it runs. `camne doctor` reports what is missing without downloading anything. Everything runs offline after that — nothing you type ever leaves the machine.

camne only prints commands, it never runs them, and anything the safety checker flags gets a `camne warning:` line above the command first.

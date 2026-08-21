#!/usr/bin/env bash
# sync this checkout to the pi and re-run the installer
set -euo pipefail
HOST="${1:-rpi.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rsync -a --delete --exclude .git --exclude __pycache__ "$SRC/" "$HOST:~/webradio/"
ssh -t "$HOST" 'sudo bash ~/webradio/deploy/install.sh'

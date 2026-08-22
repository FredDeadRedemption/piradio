#!/usr/bin/env bash
# sync this checkout to the pi and re-run the installer
set -euo pipefail
HOST="${1:-rpi.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rsync -a --delete --exclude .git --exclude __pycache__ "$SRC/" "$HOST:~/webradio/"
ssh -t "$HOST" "sudo WEBRADIO_DOMAIN='${WEBRADIO_DOMAIN:-}' WEBRADIO_LE_EMAIL='${WEBRADIO_LE_EMAIL:-}' WEBRADIO_PUBLIC_UI='${WEBRADIO_PUBLIC_UI:-}' bash ~/webradio/deploy/install.sh"

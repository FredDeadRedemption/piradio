#!/usr/bin/env bash
# sync this checkout to the host and re-run the installer
set -euo pipefail
HOST="${1:-rpi.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rsync -a --delete --exclude .git --exclude __pycache__ "$SRC/" "$HOST:~/webradio/"

# forwarded by hand: ssh does not carry them, and sudo would drop them if it did
settings=""
for name in WEBRADIO_DOMAIN WEBRADIO_LE_EMAIL WEBRADIO_PUBLIC_UI \
            WEBRADIO_NAME WEBRADIO_DESCRIPTION WEBRADIO_TZ; do
  [[ -n ${!name:-} ]] && settings+=" $(printf '%s=%q' "$name" "${!name}")"
done

ssh -t "$HOST" "sudo env$settings bash ~/webradio/deploy/install.sh"

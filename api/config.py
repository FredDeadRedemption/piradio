import os
from pathlib import Path

ROOT = Path(os.environ.get("WEBRADIO_ROOT", "/srv/webradio"))
MEDIA = ROOT / "media"
STATE = ROOT / "state"
SOCKET = ROOT / "run" / "liquidsoap.sock"

MODE_FILE = STATE / "mode"
CHANNEL_M3U = STATE / "channel.m3u"
STATE_FILE = STATE / "state.json"

ICECAST_HOST = os.environ.get("ICECAST_HOST", "127.0.0.1")
ICECAST_PORT = int(os.environ.get("ICECAST_PORT", "8000"))
ICECAST_MOUNT = os.environ.get("ICECAST_MOUNT", "/radio.mp3")
ICECAST_STATUS_URL = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"

PASSWORD = os.environ.get("WEBRADIO_PASSWORD", "")
MAX_UPLOAD_BYTES = int(os.environ.get("WEBRADIO_MAX_UPLOAD_MB", "300")) * 1024 * 1024

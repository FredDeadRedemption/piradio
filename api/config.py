import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(os.environ.get("WEBRADIO_ROOT", "/srv/webradio"))
MEDIA = ROOT / "media"
STATE = ROOT / "state"
SOCKET = ROOT / "run" / "liquidsoap.sock"

MODE_FILE = STATE / "mode"
CHANNEL_M3U = STATE / "channel.m3u"
STATE_FILE = STATE / "state.json"
SCHEDULE_FILE = STATE / "schedule.json"

NAME = os.environ.get("WEBRADIO_NAME", "webradio")
DESCRIPTION = os.environ.get("WEBRADIO_DESCRIPTION", "a small internet radio station")

ICECAST_HOST = os.environ.get("ICECAST_HOST", "127.0.0.1")
ICECAST_PORT = int(os.environ.get("ICECAST_PORT", "8000"))
ICECAST_MOUNT = os.environ.get("ICECAST_MOUNT", "/radio.mp3")
ICECAST_STATUS_URL = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"

# what listeners connect to, which is nginx rather than icecast directly
STREAM_PORT = int(os.environ.get("WEBRADIO_STREAM_PORT", ICECAST_PORT))

PASSWORD = os.environ.get("WEBRADIO_PASSWORD", "")
PORT_API = int(os.environ.get("WEBRADIO_API_PORT", "8080"))
# where listeners on the same network would reach the control interface, if it differs
PORT_ADMIN = int(os.environ.get("WEBRADIO_ADMIN_PORT", PORT_API))
DOMAIN = os.environ.get("WEBRADIO_DOMAIN", "")
MAX_UPLOAD_BYTES = int(os.environ.get("WEBRADIO_MAX_UPLOAD_MB", "300")) * 1024 * 1024
# uploads stop before the card fills, which would take the whole box down with it
MIN_FREE_BYTES = int(os.environ.get("WEBRADIO_MIN_FREE_MB", "512")) * 1024 * 1024

SCHEDULE_TICK_SECONDS = int(os.environ.get("WEBRADIO_SCHEDULE_TICK", "20"))


def _timezone() -> ZoneInfo | None:
    """None means the host's local time, which is what an unconfigured station wants."""
    name = os.environ.get("WEBRADIO_TZ", "").strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


TZ = _timezone()

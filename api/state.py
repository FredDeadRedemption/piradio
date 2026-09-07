import json

from . import library, liquidsoap
from .config import CHANNEL_M3U, MEDIA, MODE_FILE, SOCKET, STATE, STATE_FILE

MODES = ("random", "segments", "channel")
DEFAULT = {
    "mode": "random",
    "channel": None,
    "shuffle": False,
    # the scheduled slot on air, and when a manual switch last took the air from it
    "slot": None,
    "override_since": None,
}


def ensure() -> None:
    """build the directory skeleton, so a fresh volume or checkout starts working."""
    for pool in ("random", "segments", "playlists"):
        (MEDIA / pool).mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    SOCKET.parent.mkdir(parents=True, exist_ok=True)
    if not CHANNEL_M3U.exists():
        CHANNEL_M3U.write_text("")
    if not MODE_FILE.exists():
        write(read())


def read() -> dict:
    try:
        stored = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return dict(DEFAULT)
    return {k: stored.get(k, v) for k, v in DEFAULT.items()}


def wire_mode(state: dict) -> str:
    """the api models shuffle as a flag; liquidsoap models it as a separate source."""
    if state["mode"] == "channel" and state["shuffle"]:
        return "channel_shuffle"
    return state["mode"]


def write(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))
    # liquidsoap reads this at startup, so it must mirror state.json
    MODE_FILE.write_text(wire_mode(state))


def render_channel(name: str | None) -> None:
    tracks = [t["path"] for t in library.tracks("channel", name)] if name else []
    CHANNEL_M3U.write_text("\n".join(tracks) + ("\n" if tracks else ""))


def apply(state: dict, *, skip: bool = True) -> None:
    """push state to liquidsoap; playlist reloads have to precede the mode switch."""
    render_channel(state["channel"])
    liquidsoap.command("reload channel")
    liquidsoap.command(f"mode {wire_mode(state)}")
    if skip:
        liquidsoap.command("stream.skip")

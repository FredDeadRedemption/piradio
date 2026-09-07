import re
import shutil
from pathlib import Path

from .config import MEDIA

POOLS = ("random", "segments", "channel")
PLAYLISTS = MEDIA / "playlists"
CHANNEL_RE = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,47}$")
UNSAFE_RE = re.compile(r"[^A-Za-z0-9._ -]")
EXTENSIONS = (".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav")


class LibraryError(ValueError):
    pass


def pool_dir(pool: str, channel: str | None = None) -> Path:
    if pool in ("random", "segments"):
        return MEDIA / pool
    if pool != "channel":
        raise LibraryError(f"unknown pool '{pool}'")
    if not channel or not CHANNEL_RE.match(channel):
        raise LibraryError("invalid channel name")
    return PLAYLISTS / channel


def channels() -> list[str]:
    if not PLAYLISTS.is_dir():
        return []
    return sorted(d.name for d in PLAYLISTS.iterdir() if d.is_dir())


def create_channel(name: str) -> str:
    name = name.strip().lower()
    if not CHANNEL_RE.match(name):
        raise LibraryError("channel names: lowercase letters, digits, space, - and _")
    pool_dir("channel", name).mkdir(parents=True, exist_ok=True)
    return name


def delete_channel(name: str) -> None:
    shutil.rmtree(pool_dir("channel", name), ignore_errors=True)


def safe_filename(name: str) -> str:
    name = UNSAFE_RE.sub("_", Path(name).name).lstrip(".").strip() or "track"
    if not name.lower().endswith(EXTENSIONS):
        raise LibraryError(f"only {', '.join(EXTENSIONS)} files are accepted")
    return name


def unique_path(directory: Path, name: str) -> Path:
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate, n = directory / name, 1
    while candidate.exists():
        candidate = directory / f"{stem}-{n}{suffix}"
        n += 1
    return candidate


def tracks(pool: str, channel: str | None = None) -> list[dict]:
    directory = pool_dir(pool, channel)
    if not directory.is_dir():
        return []
    found = [f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONS]
    return [
        {"name": f.name, "path": str(f), "size": f.stat().st_size}
        for f in sorted(found, key=lambda f: f.name.lower())
    ]


def resolve_track(pool: str, name: str, channel: str | None = None) -> Path:
    directory = pool_dir(pool, channel)
    path = (directory / Path(name).name).resolve()
    # reject anything that escaped the pool via a crafted name
    if path.parent != directory.resolve() or not path.is_file():
        raise LibraryError("no such track")
    return path

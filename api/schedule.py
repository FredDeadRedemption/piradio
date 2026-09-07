import asyncio
import json
import logging
import re
import secrets
from datetime import date, datetime, time, timedelta

from . import library, liquidsoap, state
from .config import SCHEDULE_FILE, SCHEDULE_TICK_SECONDS, TZ

log = logging.getLogger("webradio")

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
START_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
EMPTY = {"enabled": False, "entries": []}


class ScheduleError(ValueError):
    pass


def now() -> datetime:
    """always tz-aware, so stored slot stamps stay comparable across restarts."""
    return datetime.now(TZ) if TZ else datetime.now().astimezone()


def read() -> dict:
    try:
        stored = json.loads(SCHEDULE_FILE.read_text())
    except (OSError, ValueError):
        return dict(EMPTY)
    entries = stored.get("entries")
    return {
        "enabled": bool(stored.get("enabled")),
        "entries": entries if isinstance(entries, list) else [],
    }


def write(schedule: dict) -> None:
    SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2))


def validate(payload: dict) -> dict:
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise ScheduleError("entries must be a list")
    channels = library.channels()
    parsed = [_entry(raw, channels) for raw in entries]
    return {
        "enabled": bool(payload.get("enabled")),
        "entries": sorted(parsed, key=lambda e: (e["days"][0], e["start"])),
    }


def _entry(raw: object, channels: list[str]) -> dict:
    if not isinstance(raw, dict):
        raise ScheduleError("every entry must be an object")

    days = raw.get("days")
    if not isinstance(days, list) or not days:
        raise ScheduleError("every entry needs at least one day")
    try:
        days = sorted({int(day) for day in days})
    except (TypeError, ValueError):
        raise ScheduleError("days are 0 (monday) to 6 (sunday)") from None
    if days[0] < 0 or days[-1] > 6:
        raise ScheduleError("days are 0 (monday) to 6 (sunday)")

    start = str(raw.get("start", ""))
    if not START_RE.match(start):
        raise ScheduleError(f"'{start}' is not a 24-hour HH:MM time")

    mode = raw.get("mode")
    if mode not in state.MODES:
        raise ScheduleError(f"mode must be one of {', '.join(state.MODES)}")

    channel = raw.get("channel") or None
    if mode == "channel" and channel not in channels:
        raise ScheduleError(f"unknown channel '{channel}'")
    if mode != "channel":
        channel = None

    return {
        "id": str(raw.get("id") or secrets.token_hex(4)),
        "days": days,
        "start": start,
        "mode": mode,
        "channel": channel,
        "shuffle": bool(raw.get("shuffle")),
    }


def _moment(reference: datetime, day_offset: int, start: str) -> datetime:
    """a start time on a day relative to reference, counted in dates rather than hours."""
    hour, minute = (int(part) for part in start.split(":"))
    when: date = reference.date() + timedelta(days=day_offset)
    return datetime.combine(when, time(hour, minute), tzinfo=reference.tzinfo)


def _started(entry: dict, at: datetime) -> datetime:
    """the most recent start of this entry at or before `at`."""
    starts = []
    for day in entry["days"]:
        back = (at.weekday() - day) % 7
        moment = _moment(at, -back, entry["start"])
        starts.append(moment if moment <= at else _moment(at, -back - 7, entry["start"]))
    return max(starts)


def _starts_next(entry: dict, at: datetime) -> datetime:
    starts = []
    for day in entry["days"]:
        ahead = (day - at.weekday()) % 7
        moment = _moment(at, ahead, entry["start"])
        starts.append(moment if moment > at else _moment(at, ahead + 7, entry["start"]))
    return min(starts)


def current(schedule: dict, at: datetime | None = None) -> tuple[dict | None, datetime | None]:
    """what the schedule says should be on air, and when that slot began."""
    at = at or now()
    # the index breaks ties on identical start times without comparing the entries
    entries = enumerate(schedule["entries"])
    slots = [(_started(entry, at), index, entry) for index, entry in entries]
    if not slots:
        return None, None
    started, _, entry = max(slots)
    return entry, started


def upcoming(schedule: dict, at: datetime | None = None) -> tuple[dict | None, datetime | None]:
    at = at or now()
    entries = enumerate(schedule["entries"])
    slots = [(_starts_next(entry, at), index, entry) for index, entry in entries]
    if not slots:
        return None, None
    starts, _, entry = min(slots)
    return entry, starts


def tick() -> dict | None:
    """put the scheduled programming on air if a slot has begun since the last one applied."""
    schedule = read()
    if not schedule["enabled"]:
        return None
    entry, started = current(schedule)
    if entry is None:
        return None

    live = state.read()
    if live["slot"] == started.isoformat():
        return None
    # a manual switch owns the air for the rest of its slot
    override = _parse(live["override_since"])
    if override and override >= started:
        return None

    live |= {
        "mode": entry["mode"],
        "channel": entry["channel"] or live["channel"],
        "shuffle": entry["shuffle"],
        "slot": started.isoformat(),
        "override_since": None,
    }
    state.write(live)
    try:
        state.apply(live)
    except liquidsoap.LiquidsoapError as exc:
        # the mode file is already written, so a restarting playout picks the slot up anyway
        log.warning("scheduled switch to %s not pushed to playout: %s", entry["mode"], exc)
    return entry


def _parse(stamp: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp) if stamp else None
    except ValueError:
        return None


async def run() -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("schedule tick failed")
        await asyncio.sleep(SCHEDULE_TICK_SECONDS)

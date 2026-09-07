from datetime import UTC, datetime, timedelta

import pytest

from api import library, schedule, state


# 2026-09-07 is a monday, so weekday offsets read as calendar days
def moment(weekday: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 7, hour, minute, tzinfo=UTC) + timedelta(days=weekday)


def entry(days, start, mode="random", channel=None, shuffle=False):
    return {"days": days, "start": start, "mode": mode, "channel": channel, "shuffle": shuffle}


def saved(*entries, enabled=True):
    return schedule.validate({"enabled": enabled, "entries": list(entries)})


def test_validate_fills_in_ids_and_sorts_by_day_then_time():
    result = saved(entry([3], "22:00"), entry([0], "07:00"), entry([0], "06:00"))
    assert [e["start"] for e in result["entries"]] == ["06:00", "07:00", "22:00"]
    assert all(e["id"] for e in result["entries"])


@pytest.mark.parametrize(
    "bad",
    [
        entry([], "07:00"),
        entry([7], "07:00"),
        entry([-1], "07:00"),
        entry([0], "24:00"),
        entry([0], "7:00"),
        entry([0], "0700"),
        entry([0], "07:00", mode="nonsense"),
        entry([0], "07:00", mode="channel", channel="missing"),
    ],
)
def test_validate_rejects_nonsense(bad):
    with pytest.raises(schedule.ScheduleError):
        saved(bad)


def test_a_channel_slot_needs_a_channel_that_exists():
    library.create_channel("jazz")
    result = saved(entry([0], "07:00", mode="channel", channel="jazz", shuffle=True))
    assert result["entries"][0]["channel"] == "jazz"


def test_shuffle_and_channel_are_dropped_for_pool_modes():
    result = saved(entry([0], "07:00", mode="segments", channel="jazz"))
    assert result["entries"][0]["channel"] is None


def test_current_picks_the_most_recent_start():
    plan = saved(entry([0], "08:00"), entry([0], "20:00", mode="segments"))
    chosen, started = schedule.current(plan, moment(0, 12))
    assert chosen["start"] == "08:00"
    assert started == moment(0, 8)


def test_current_reaches_back_into_last_week_before_the_first_slot():
    plan = saved(entry([0], "08:00"), entry([0], "20:00", mode="segments"))
    chosen, started = schedule.current(plan, moment(0, 6))
    assert chosen["start"] == "20:00"
    assert started == moment(-7, 20)


def test_current_handles_an_entry_with_several_days():
    plan = saved(entry([0, 2], "08:00"))
    _, started = schedule.current(plan, moment(2, 9))
    assert started == moment(2, 8)


def test_upcoming_is_the_next_start_after_now():
    plan = saved(entry([0], "08:00"), entry([0], "20:00", mode="segments"))
    chosen, starts = schedule.upcoming(plan, moment(0, 12))
    assert chosen["start"] == "20:00"
    assert starts == moment(0, 20)


def test_upcoming_rolls_over_to_next_week():
    plan = saved(entry([0], "08:00"))
    _, starts = schedule.upcoming(plan, moment(0, 9))
    assert starts == moment(7, 8)


def test_tick_puts_the_current_slot_on_air(monkeypatch):
    schedule.write(saved(entry([0], "08:00", mode="segments")))
    monkeypatch.setattr(schedule, "now", lambda: moment(0, 12))

    assert schedule.tick()["mode"] == "segments"
    assert state.read()["mode"] == "segments"
    assert state.read()["slot"] == moment(0, 8).isoformat()


def test_tick_does_nothing_while_the_schedule_is_off(monkeypatch):
    schedule.write(saved(entry([0], "08:00", mode="segments"), enabled=False))
    monkeypatch.setattr(schedule, "now", lambda: moment(0, 12))

    assert schedule.tick() is None
    assert state.read()["mode"] == "random"


def test_a_manual_switch_holds_the_air_for_the_rest_of_its_slot(monkeypatch):
    schedule.write(saved(entry([0], "08:00", mode="segments"), entry([0], "20:00")))
    monkeypatch.setattr(schedule, "now", lambda: moment(0, 12))
    schedule.tick()

    state.write(state.read() | {"mode": "random", "override_since": moment(0, 13).isoformat()})
    monkeypatch.setattr(schedule, "now", lambda: moment(0, 14))
    assert schedule.tick() is None
    assert state.read()["mode"] == "random"


def test_the_next_slot_takes_the_air_back_from_a_manual_switch(monkeypatch):
    schedule.write(saved(entry([0], "08:00"), entry([0], "20:00", mode="segments")))
    state.write(state.read() | {"override_since": moment(0, 13).isoformat()})

    monkeypatch.setattr(schedule, "now", lambda: moment(0, 20, 30))
    assert schedule.tick()["mode"] == "segments"
    assert state.read()["override_since"] is None


def test_tick_is_idempotent_inside_one_slot(monkeypatch, playout):
    schedule.write(saved(entry([0], "08:00", mode="segments")))
    monkeypatch.setattr(schedule, "now", lambda: moment(0, 12))

    schedule.tick()
    playout.clear()
    assert schedule.tick() is None
    assert playout == []

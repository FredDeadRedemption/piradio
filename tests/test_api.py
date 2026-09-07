from api import library, schedule, state


def upload(client, auth, pool="random", name="track.mp3", channel=None):
    data = {"pool": pool} | ({"channel": channel} if channel else {})
    return client.post(
        "/api/tracks",
        data=data,
        files=[("files", (name, b"\xff\xfb\x00" * 64, "audio/mpeg"))],
        auth=auth,
    )


def test_the_control_api_needs_a_password(client):
    assert client.get("/api/state").status_code == 401
    assert client.post("/api/skip").status_code == 401


def test_the_listener_endpoint_does_not(client):
    body = client.get("/api/now").json()
    assert body["station"]["name"]
    assert body["url"].endswith("/radio.mp3")


def test_state_reports_the_station_and_its_channels(client, auth):
    library.create_channel("jazz")
    body = client.get("/api/state", auth=auth).json()
    assert body["channels"] == ["jazz"]
    assert body["playout"] is True
    assert body["schedule"] == {"enabled": False, "manual": False, "next": None}


def test_uploading_then_deleting_a_track(client, auth):
    assert upload(client, auth).json() == {"stored": ["track.mp3"], "rejected": []}
    assert [
        t["name"] for t in client.get("/api/tracks?pool=random", auth=auth).json()["tracks"]
    ] == ["track.mp3"]

    assert client.delete("/api/tracks?pool=random&name=track.mp3", auth=auth).status_code == 204
    assert client.get("/api/tracks?pool=random", auth=auth).json()["tracks"] == []


def test_uploads_that_are_not_audio_are_reported_not_stored(client, auth):
    body = upload(client, auth, name="payload.txt").json()
    assert body["stored"] == []
    assert body["rejected"][0]["name"] == "payload.txt"


def test_switching_mode_reaches_playout(client, auth, playout):
    assert client.post("/api/mode", json={"mode": "segments"}, auth=auth).status_code == 200
    assert state.read()["mode"] == "segments"
    assert "mode segments" in playout


def test_switching_mode_by_hand_records_an_override(client, auth):
    client.post("/api/mode", json={"mode": "segments"}, auth=auth)
    assert state.read()["override_since"] is not None


def test_an_unknown_mode_is_refused(client, auth):
    assert client.post("/api/mode", json={"mode": "nonsense"}, auth=auth).status_code == 400


def test_a_channel_mode_needs_a_channel_that_exists(client, auth):
    assert client.post("/api/mode", json={"mode": "channel"}, auth=auth).status_code == 400


def test_saving_a_schedule_puts_the_current_slot_on_air(client, auth):
    body = client.put(
        "/api/schedule",
        json={
            "enabled": True,
            "entries": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "mode": "segments"}],
        },
        auth=auth,
    ).json()

    assert body["enabled"] is True
    assert body["entries"][0]["id"]
    assert state.read()["mode"] == "segments"


def test_a_schedule_the_station_cannot_play_is_refused(client, auth):
    response = client.put(
        "/api/schedule",
        json={"enabled": True, "entries": [{"days": [0], "start": "25:00", "mode": "random"}]},
        auth=auth,
    )
    assert response.status_code == 400
    assert schedule.read()["entries"] == []


def test_deleting_a_channel_drops_the_slots_that_pointed_at_it(client, auth):
    library.create_channel("jazz")
    client.put(
        "/api/schedule",
        json={
            "enabled": True,
            "entries": [
                {"days": [0], "start": "07:00", "mode": "channel", "channel": "jazz"},
                {"days": [0], "start": "09:00", "mode": "random"},
            ],
        },
        auth=auth,
    )

    assert client.delete("/api/channels/jazz", auth=auth).status_code == 204
    assert [e["mode"] for e in schedule.read()["entries"]] == ["random"]


def test_deleting_the_channel_on_air_falls_back(client, auth):
    library.create_channel("jazz")
    client.post("/api/mode", json={"mode": "channel", "channel": "jazz"}, auth=auth)

    client.delete("/api/channels/jazz", auth=auth)
    assert state.read()["mode"] == "random"
    assert state.read()["channel"] is None

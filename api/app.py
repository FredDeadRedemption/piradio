import logging
import secrets
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import library, liquidsoap, state
from .config import (
    ICECAST_MOUNT,
    ICECAST_STATUS_URL,
    MAX_UPLOAD_BYTES,
    PASSWORD,
    STREAM_PORT,
)

app = FastAPI(title="webradio", docs_url=None, redoc_url=None)
log = logging.getLogger("webradio")
STATIC = Path(__file__).parent / "static"
basic = HTTPBasic(auto_error=False)


def auth(credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)]) -> None:
    if not PASSWORD:
        return
    if not credentials or not secrets.compare_digest(credentials.password, PASSWORD):
        raise HTTPException(401, "unauthorized", {"WWW-Authenticate": "Basic"})


guard = [Depends(auth)]


async def icecast_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            payload = (await client.get(ICECAST_STATUS_URL)).json()
    except (httpx.HTTPError, ValueError):
        return {"online": False, "title": None, "listeners": 0}

    sources = payload.get("icestats", {}).get("source") or []
    if isinstance(sources, dict):
        sources = [sources]
    for source in sources:
        if str(source.get("listenurl", "")).endswith(ICECAST_MOUNT):
            return {
                "online": True,
                "title": source.get("title") or source.get("yp_currently_playing"),
                "listeners": source.get("listeners", 0),
            }
    return {"online": False, "title": None, "listeners": 0}


@app.get("/", dependencies=guard, include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/app.js", include_in_schema=False)
def script() -> FileResponse:
    return FileResponse(STATIC / "app.js", media_type="application/javascript")


@app.get("/style.css", include_in_schema=False)
def stylesheet() -> FileResponse:
    return FileResponse(STATIC / "style.css", media_type="text/css")


@app.get("/api/state", dependencies=guard)
async def get_state() -> dict:
    current = state.read()
    try:
        liquidsoap.command("current_mode")
        playout = True
    except liquidsoap.LiquidsoapError:
        playout = False
    return {
        **current,
        "channels": library.channels(),
        "playout": playout,
        "stream": {"port": STREAM_PORT, "mount": ICECAST_MOUNT},
        "icecast": await icecast_status(),
    }


@app.post("/api/mode", dependencies=guard)
def set_mode(payload: dict) -> dict:
    mode = payload.get("mode")
    if mode not in state.MODES:
        raise HTTPException(400, f"mode must be one of {', '.join(state.MODES)}")

    current = state.read()
    current["mode"] = mode
    if mode == "channel":
        channel = payload.get("channel") or current["channel"]
        if channel not in library.channels():
            raise HTTPException(400, "unknown channel")
        current["channel"] = channel
    if "shuffle" in payload:
        current["shuffle"] = bool(payload["shuffle"])

    state.write(current)
    try:
        state.apply(current)
    except liquidsoap.LiquidsoapError as exc:
        raise HTTPException(503, str(exc)) from exc
    return current


@app.post("/api/skip", dependencies=guard)
def skip() -> dict:
    try:
        liquidsoap.command("stream.skip")
    except liquidsoap.LiquidsoapError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"ok": True}


@app.get("/api/tracks", dependencies=guard)
def list_tracks(pool: str, channel: str | None = None) -> dict:
    try:
        return {"tracks": library.tracks(pool, channel)}
    except library.LibraryError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/tracks", dependencies=guard)
async def upload(
    pool: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
    channel: Annotated[str | None, Form()] = None,
) -> dict:
    try:
        directory = library.pool_dir(pool, channel)
    except library.LibraryError as exc:
        raise HTTPException(400, str(exc)) from exc
    directory.mkdir(parents=True, exist_ok=True)

    stored, rejected = [], []
    for upload_file in files:
        try:
            name = library.safe_filename(upload_file.filename or "")
        except library.LibraryError as exc:
            rejected.append({"name": upload_file.filename, "reason": str(exc)})
            continue

        target = library.unique_path(directory, name)
        written = 0
        try:
            with target.open("wb") as handle:
                while chunk := await upload_file.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise library.LibraryError("file too large")
                    handle.write(chunk)
        except library.LibraryError as exc:
            target.unlink(missing_ok=True)
            rejected.append({"name": upload_file.filename, "reason": str(exc)})
            continue
        stored.append(target.name)

    refresh(pool, channel)
    return {"stored": stored, "rejected": rejected}


@app.delete("/api/tracks", dependencies=guard)
def delete_track(pool: str, name: str, channel: str | None = None) -> Response:
    try:
        library.resolve_track(pool, name, channel).unlink()
    except library.LibraryError as exc:
        raise HTTPException(404, str(exc)) from exc
    refresh(pool, channel)
    return Response(status_code=204)


@app.get("/api/channels", dependencies=guard)
def list_channels() -> dict:
    return {"channels": library.channels()}


@app.post("/api/channels", dependencies=guard)
def add_channel(payload: dict) -> dict:
    try:
        return {"channel": library.create_channel(payload.get("name", ""))}
    except library.LibraryError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/channels/{name}", dependencies=guard)
def remove_channel(name: str) -> Response:
    try:
        library.delete_channel(name)
    except library.LibraryError as exc:
        raise HTTPException(400, str(exc)) from exc

    current = state.read()
    if current["channel"] == name:
        current["channel"] = next(iter(library.channels()), None)
        if current["mode"] == "channel" and current["channel"] is None:
            current["mode"] = "random"
        state.write(current)
        try:
            state.apply(current)
        except liquidsoap.LiquidsoapError:
            pass
    return Response(status_code=204)


def refresh(pool: str, channel: str | None) -> None:
    """tell liquidsoap the pool changed; failing here only delays pickup, so never fatal."""
    current = state.read()
    try:
        if pool != "channel":
            liquidsoap.command(f"reload {pool}")
        elif current["channel"] == channel:
            state.render_channel(channel)
            liquidsoap.command("reload channel")
    except liquidsoap.LiquidsoapError as exc:
        log.warning("playout reload failed: %s", exc)

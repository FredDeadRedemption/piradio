import os
import shutil
import tempfile
from pathlib import Path

import pytest

# config reads the environment at import time, so the test root has to be set first
ROOT = Path(tempfile.mkdtemp(prefix="webradio-tests-"))
os.environ["WEBRADIO_ROOT"] = str(ROOT)
os.environ["WEBRADIO_PASSWORD"] = "secret"
os.environ["WEBRADIO_TZ"] = "UTC"

from api import liquidsoap, state  # noqa: E402


@pytest.fixture(autouse=True)
def playout(monkeypatch):
    """an empty station and a playout that answers every command, per test."""
    shutil.rmtree(ROOT, ignore_errors=True)
    state.ensure()

    sent = []

    def command(line, timeout=3.0):
        sent.append(line)
        return "OK"

    monkeypatch.setattr(liquidsoap, "command", command)
    return sent


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from api.app import app

    # not a context manager: the scheduler task must not tick underneath the assertions
    return TestClient(app)


@pytest.fixture
def auth():
    return ("station", "secret")

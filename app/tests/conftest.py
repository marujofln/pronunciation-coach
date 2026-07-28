import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="pronunciation_coach_test_"))
os.environ["PRONUNCIATION_COACH_DATA_DIR"] = str(_TEST_DATA_DIR)

# Dummy auth config: authlib only fetches OIDC metadata lazily, on the first
# call to authorize_redirect/authorize_access_token — no test exercises the
# real login flow, so these values are never actually used over the network.
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")
os.environ.setdefault(
    "AUTHENTIK_ISSUER", "http://authentik.invalid/application/o/test/"
)
os.environ.setdefault("AUTHENTIK_CLIENT_ID", "test-client-id")
os.environ.setdefault("AUTHENTIK_CLIENT_SECRET", "test-client-secret")

import threading
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, Route
from sqlmodel import Session

from app import config
from app.auth import get_current_user
from app.db import engine
from app.main import app
from app.models import User


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        with Session(engine) as session:
            user = User(sub="test-sub", email="tester@example.com")
            session.add(user)
            session.commit()
            session.refresh(user)
        app.dependency_overrides[get_current_user] = lambda: user
        yield test_client
        app.dependency_overrides.pop(get_current_user, None)


# --- Frontend (browser) test support -------------------------------------
#
# The browser tests deliberately do NOT run the FastAPI app: they serve
# frontend/ from a bare static file server and intercept every /api/* call in
# the browser. That keeps them hermetic and, more importantly, keeps the
# expensive Whisper/G2p model load out of the frontend test run entirely.


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        """Silence the per-request stderr logging SimpleHTTPRequestHandler does."""


@pytest.fixture(scope="session")
def frontend_server():
    """Serve frontend/ over HTTP so the browser sees the real shipped files."""
    handler = partial(_QuietHandler, directory=str(config.BASE_DIR / "frontend"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """Give Chromium a synthetic microphone with permission pre-granted.

    This is what lets the tests drive the *real* MediaRecorder instead of
    stubbing it out, so app.js runs exactly as it does in a browser.
    """
    return {
        **browser_type_launch_args,
        "args": [
            *browser_type_launch_args.get("args", []),
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
        ],
    }


@dataclass
class Canned:
    """A canned response for one API endpoint."""

    status: int = 200
    json: Any = None
    body: str | None = None
    abort: bool = False


def json_error(status: int) -> Canned:
    return Canned(status=status, json={"detail": "nope"})


def network_error() -> Canned:
    """A failed request — what makes fetch() itself reject.

    loadHistory/loadStats have no res.ok check and only catch thrown errors,
    so a plain 500 with a valid JSON body would NOT reach their fallbacks.
    """
    return Canned(abort=True)


def malformed_json() -> Canned:
    return Canned(body="<html>not json</html>")


@dataclass
class RecordedRequest:
    method: str
    url: str
    path: str
    post_data: bytes | None


DEFAULT_ME = {"id": 1, "email": "tester@example.com"}
DEFAULT_PHRASE = {
    "id": 7,
    "text": "She sells seashells by the seashore",
    "difficulty": "hard",
    "category": "tongue twister",
    "created_at": "2026-01-01T00:00:00",
}
DEFAULT_STATS = {"total_attempts": 0, "average_score": None, "per_phrase": []}
DEFAULT_RESULT = {
    "attempt_id": 1,
    "phrase_id": 7,
    "phrase_text": DEFAULT_PHRASE["text"],
    "transcript": "she sells seashells by the seashore",
    "score": 87.5,
    "word_feedback": [],
    "created_at": "2026-01-01T00:00:00",
}


@dataclass
class ApiMock:
    """Canned /api/* responses plus a log of what the frontend requested.

    Each endpoint slot holds either a plain payload (served as 200 JSON), a
    `Canned`, or a callable taking the request and returning either of those
    (use a callable when successive calls to one endpoint must differ).
    """

    me: Any = field(default_factory=lambda: dict(DEFAULT_ME))
    phrase: Any = field(default_factory=lambda: dict(DEFAULT_PHRASE))
    attempts: Any = field(default_factory=list)
    stats: Any = field(default_factory=lambda: dict(DEFAULT_STATS))
    result: Any = field(default_factory=lambda: dict(DEFAULT_RESULT))
    requests: list[RecordedRequest] = field(default_factory=list)

    def install(self, page: Page) -> None:
        # A single dispatching route rather than one page.route() per endpoint:
        # Playwright matches routes in reverse registration order, so separate
        # patterns for /api/attempts/stats and /api/attempts/?limit=20 would
        # shadow each other depending on declaration order.
        page.route("**/api/**", self._handle)

    def requests_to(self, path: str) -> list[RecordedRequest]:
        return [r for r in self.requests if r.path == path]

    def _slot_for(self, recorded: RecordedRequest) -> Any:
        if recorded.path == "/api/me":
            return self.me
        if recorded.path == "/api/phrases/random":
            return self.phrase
        if recorded.path == "/api/attempts/stats":
            return self.stats
        if recorded.path == "/api/attempts/":
            return self.result if recorded.method == "POST" else self.attempts
        return json_error(404)

    def _handle(self, route: Route) -> None:
        request = route.request
        recorded = RecordedRequest(
            method=request.method,
            url=request.url,
            path=urlparse(request.url).path,
            post_data=request.post_data_buffer,
        )
        self.requests.append(recorded)

        value = self._slot_for(recorded)
        if callable(value):
            value = value(recorded)
        if not isinstance(value, Canned):
            value = Canned(json=value)

        if value.abort:
            route.abort()
        elif value.body is not None:
            route.fulfill(status=value.status, body=value.body)
        else:
            route.fulfill(status=value.status, json=value.json)


@pytest.fixture
def api(page: Page) -> ApiMock:
    """Intercept /api/* before anything navigates.

    app.js kicks off loadCurrentUser/loadRandomPhrase/loadHistory/loadStats at
    load time, so routing must already be installed when page.goto() runs.
    """
    mock = ApiMock()
    mock.install(page)
    return mock

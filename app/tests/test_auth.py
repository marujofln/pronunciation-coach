import asyncio
import re
from urllib.parse import parse_qs, urlparse

from sqlmodel import Session

from app import config
from app.auth import get_current_user, require_web_session
from app.db import engine
from app.main import app
from app.models import User
from app.routers import auth as auth_router
from app.tests.test_api import make_synthetic_wav

FRONTEND_DIR = config.BASE_DIR / "frontend"


def test_api_requires_auth_without_session(client):
    previous = app.dependency_overrides.pop(get_current_user, None)
    try:
        assert client.get("/api/phrases/").status_code == 401
        assert client.get("/api/attempts/").status_code == 401
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_user] = previous


def test_me_returns_current_user(client):
    res = client.get("/api/me")
    assert res.status_code == 200
    me = res.json()
    assert me["email"] == "tester@example.com"
    assert isinstance(me["id"], int)


def test_attempts_are_scoped_per_user(client):
    with Session(engine) as session:
        other_user = User(sub="other-test-sub", email="other@example.com")
        session.add(other_user)
        session.commit()
        session.refresh(other_user)

    original_override = app.dependency_overrides.get(get_current_user)

    phrase = client.get("/api/phrases/random").json()
    wav_bytes = make_synthetic_wav()
    client.post(
        "/api/attempts/",
        data={"phrase_id": str(phrase["id"])},
        files={"audio": ("recording.wav", wav_bytes, "audio/wav")},
    )
    original_count = len(client.get("/api/attempts/", params={"limit": 200}).json())

    try:
        app.dependency_overrides[get_current_user] = lambda: other_user

        other_history_before = client.get(
            "/api/attempts/", params={"limit": 200}
        ).json()
        assert len(other_history_before) == 0

        client.post(
            "/api/attempts/",
            data={"phrase_id": str(phrase["id"])},
            files={"audio": ("recording.wav", wav_bytes, "audio/wav")},
        )
        other_history_after = client.get("/api/attempts/", params={"limit": 200}).json()
        assert len(other_history_after) == 1

        other_stats = client.get("/api/attempts/stats").json()
        assert other_stats["total_attempts"] == 1
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override

    final_history = client.get("/api/attempts/", params={"limit": 200}).json()
    assert len(final_history) == original_count


END_SESSION = "http://authentik.invalid/application/o/pronunciation-coach/end-session/"


class _FakeRequest:
    """_end_session_url only ever reads base_url off the request."""

    base_url = "http://testserver/"


def _stub_metadata(monkeypatch, metadata: dict | None, *, raises: bool = False):
    async def load_server_metadata():
        if raises:
            raise OSError("authentik unreachable")
        return metadata

    monkeypatch.setattr(
        auth_router.oauth.authentik, "load_server_metadata", load_server_metadata
    )


def _end_session_url(id_token: str | None) -> str:
    return asyncio.run(auth_router._end_session_url(_FakeRequest(), id_token))


def test_logout_redirects_to_the_idp_end_session_endpoint(monkeypatch):
    """Clearing only our own cookie lets Authentik silently re-authorize."""
    _stub_metadata(monkeypatch, {"end_session_endpoint": END_SESSION})

    parsed = urlparse(_end_session_url("an-id-token"))

    assert parsed.path == "/application/o/pronunciation-coach/end-session/"
    query = parse_qs(parsed.query)
    assert query["post_logout_redirect_uri"] == ["http://testserver/"]
    # Without the hint Authentik interrupts logout with a confirmation page.
    assert query["id_token_hint"] == ["an-id-token"]


def test_logout_omits_id_token_hint_when_absent(monkeypatch):
    _stub_metadata(monkeypatch, {"end_session_endpoint": END_SESSION})

    assert "id_token_hint" not in parse_qs(urlparse(_end_session_url(None)).query)


def test_logout_falls_back_to_home_when_idp_is_unreachable(monkeypatch):
    """A logout that 500s because the IdP is down is worse than a local one."""
    _stub_metadata(monkeypatch, None, raises=True)

    assert _end_session_url("tok") == "/"


def test_logout_falls_back_when_metadata_has_no_end_session(monkeypatch):
    _stub_metadata(monkeypatch, {})

    assert _end_session_url("tok") == "/"


def test_logout_clears_the_local_session(client):
    """Whatever the IdP does, our own cookie must not survive logout."""
    res = client.get("/auth/logout", follow_redirects=False)

    assert res.status_code in (302, 307)
    # Starlette clears a signed session by emptying the cookie.
    assert client.cookies.get("session") in (None, "", '""')


def test_frontend_redirects_to_login_without_session(client):
    # require_web_session is never overridden by the client fixture, so the
    # frontend router is genuinely unauthenticated here.
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"].startswith("/auth/login?next=")


def test_frontend_is_served_with_a_session(client):
    app.dependency_overrides[require_web_session] = lambda: None
    try:
        index = client.get("/")
        assert index.status_code == 200
        assert "<title>Pronunciation Coach</title>" in index.text

        for path in ("/app.js", "/style.css"):
            asset = client.get(path)
            assert asset.status_code == 200, path
    finally:
        app.dependency_overrides.pop(require_web_session, None)


def test_docs_are_not_behind_the_frontend_auth_gate(client):
    # The Dockerfile healthcheck hits /docs unauthenticated; keep that true.
    assert client.get("/docs").status_code == 200


def test_index_html_defines_every_element_id_app_js_uses():
    """app.js resolves all 21 elements at load; a renamed id blanks the page."""
    app_js = (FRONTEND_DIR / "app.js").read_text()
    index_html = (FRONTEND_DIR / "index.html").read_text()

    element_ids = set(re.findall(r'getElementById\("([^"]+)"\)', app_js))
    assert element_ids, "no getElementById calls found — did app.js change shape?"

    missing = [i for i in sorted(element_ids) if f'id="{i}"' not in index_html]
    assert not missing, f"ids used by app.js but absent from index.html: {missing}"

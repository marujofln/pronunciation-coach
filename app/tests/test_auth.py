import re

from sqlmodel import Session

from app import config
from app.auth import get_current_user, require_web_session
from app.db import engine
from app.main import app
from app.models import User
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

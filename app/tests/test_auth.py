from sqlmodel import Session

from app.auth import get_current_user
from app.db import engine
from app.main import app
from app.models import User
from app.tests.test_api import make_synthetic_wav


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

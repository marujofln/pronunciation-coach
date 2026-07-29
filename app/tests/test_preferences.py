from sqlmodel import Session, delete

from app.auth import get_current_user
from app.db import engine
from app.main import app
from app.models import User, UserPreference


def reset_preferences():
    """Wipe stored preferences so each test starts from the never-chosen state."""
    with Session(engine) as session:
        session.exec(delete(UserPreference))
        session.commit()


def test_categories_lists_distinct_seeded_categories(client):
    res = client.get("/api/phrases/categories")
    assert res.status_code == 200
    categories = res.json()

    assert "tongue-twisters" in categories
    assert len(categories) == len(set(categories))
    assert categories == sorted(categories)
    assert None not in categories


def test_preferences_default_to_no_filters(client):
    reset_preferences()

    res = client.get("/api/me/preferences")

    assert res.status_code == 200
    assert res.json() == {"difficulty": None, "category": None}


def test_preferences_round_trip(client):
    reset_preferences()

    put = client.put(
        "/api/me/preferences", json={"difficulty": "hard", "category": "business"}
    )
    assert put.status_code == 200
    assert put.json() == {"difficulty": "hard", "category": "business"}

    # The point of the feature: the choice survives into a later request.
    assert client.get("/api/me/preferences").json() == {
        "difficulty": "hard",
        "category": "business",
    }


def test_updating_preferences_replaces_rather_than_accumulates(client):
    reset_preferences()
    client.put("/api/me/preferences", json={"difficulty": "hard", "category": "food"})

    res = client.put("/api/me/preferences", json={"difficulty": "easy"})

    assert res.json() == {"difficulty": "easy", "category": None}


def test_empty_category_is_stored_as_no_filter(client):
    """The "Any" option of an HTML <select> submits "", not null."""
    reset_preferences()

    res = client.put("/api/me/preferences", json={"difficulty": None, "category": ""})

    assert res.json()["category"] is None


def test_unknown_difficulty_is_rejected(client):
    assert (
        client.put("/api/me/preferences", json={"difficulty": "impossible"}).status_code
        == 422
    )


def test_preferences_are_scoped_per_user(client):
    reset_preferences()
    client.put(
        "/api/me/preferences", json={"difficulty": "hard", "category": "business"}
    )

    with Session(engine) as session:
        other_user = User(sub="prefs-other-sub", email="prefs-other@example.com")
        session.add(other_user)
        session.commit()
        session.refresh(other_user)

    original_override = app.dependency_overrides.get(get_current_user)
    try:
        app.dependency_overrides[get_current_user] = lambda: other_user

        assert client.get("/api/me/preferences").json() == {
            "difficulty": None,
            "category": None,
        }
        client.put("/api/me/preferences", json={"difficulty": "easy"})
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override

    assert client.get("/api/me/preferences").json() == {
        "difficulty": "hard",
        "category": "business",
    }


def test_preferences_require_authentication(client):
    previous = app.dependency_overrides.pop(get_current_user, None)
    try:
        assert client.get("/api/me/preferences").status_code == 401
        assert client.put("/api/me/preferences", json={}).status_code == 401
        assert client.get("/api/phrases/categories").status_code == 401
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_user] = previous

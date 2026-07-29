from sqlmodel import Session, select

from app.db import engine
from app.models import Difficulty, Phrase
from app.seed_data import PHRASES, seed_phrases


def test_seed_data_is_internally_consistent():
    texts = [p["text"] for p in PHRASES]
    assert len(texts) == len(set(texts)), "phrase.text is unique in the database"

    categories = {p["category"] for p in PHRASES}
    assert len(categories) >= 20
    assert all(c == c.lower() and " " not in c for c in categories), (
        "slugs are lowercase and hyphenated — they reach the UI as option values"
    )

    covered = {(p["category"], p["difficulty"]) for p in PHRASES}
    missing = [
        (category, difficulty)
        for category in categories
        for difficulty in Difficulty
        if (category, difficulty) not in covered
    ]
    assert missing == []


def test_seeding_retags_a_phrase_whose_category_changed(client):
    """Seeding is keyed on `text`, so edits need an explicit reconcile pass."""
    with Session(engine) as session:
        # order_by is load-bearing: Postgres guarantees no ordering for an
        # unordered SELECT, and this test *mutates* the row it picks.
        row = session.exec(
            select(Phrase)
            .where(Phrase.category == "information-technology")
            .order_by(Phrase.id)
        ).first()
        assert row is not None
        text, before = row.text, session.exec(select(Phrase)).all()

        row.category = "technology"
        row.difficulty = Difficulty.hard
        session.add(row)
        session.commit()

        seed_phrases(session)

        retagged = session.exec(select(Phrase).where(Phrase.text == text)).one()
        assert retagged.category == "information-technology"
        assert len(session.exec(select(Phrase)).all()) == len(before), (
            "reconciling must not insert a duplicate row"
        )

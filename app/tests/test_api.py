import io
import math
import struct
import wave


def make_synthetic_wav(seconds: float = 1.0, freq: float = 220.0) -> bytes:
    sample_rate = 16000
    n_samples = int(sample_rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            value = int(3000 * math.sin(2 * math.pi * freq * i / sample_rate))
            frames += struct.pack("<h", value)
        wav_file.writeframes(bytes(frames))
    return buf.getvalue()


def test_list_phrases_returns_seeded_phrases(client):
    res = client.get("/api/phrases/")
    assert res.status_code == 200
    phrases = res.json()
    assert len(phrases) >= 120
    assert {"id", "text", "difficulty", "category", "created_at"} <= phrases[0].keys()


def test_every_category_covers_every_difficulty(client):
    """A category missing a difficulty makes that filter combination 404."""
    categories = client.get("/api/phrases/categories").json()
    assert len(categories) >= 20

    empty = [
        (category, difficulty)
        for category in categories
        for difficulty in ("easy", "medium", "hard")
        if client.get(
            "/api/phrases/random",
            params={"category": category, "difficulty": difficulty},
        ).status_code
        != 200
    ]
    assert empty == []


def test_categories_lists_distinct_seeded_categories(client):
    res = client.get("/api/phrases/categories")
    assert res.status_code == 200
    categories = res.json()

    assert "tongue-twisters" in categories
    assert len(categories) == len(set(categories))
    assert categories == sorted(categories)
    assert None not in categories


def test_technology_category_was_renamed(client):
    categories = client.get("/api/phrases/categories").json()

    assert "information-technology" in categories
    assert "technology" not in categories


def test_list_phrases_filters_by_difficulty(client):
    res = client.get("/api/phrases/", params={"difficulty": "easy"})
    assert res.status_code == 200
    phrases = res.json()
    assert len(phrases) > 0
    assert all(p["difficulty"] == "easy" for p in phrases)


def test_random_phrase_returns_one_matching_phrase(client):
    res = client.get("/api/phrases/random", params={"difficulty": "hard"})
    assert res.status_code == 200
    phrase = res.json()
    assert phrase["difficulty"] == "hard"


def test_random_phrase_404_when_no_match(client):
    res = client.get(
        "/api/phrases/random", params={"category": "definitely-not-a-real-category"}
    )
    assert res.status_code == 404


def test_submit_attempt_end_to_end(client):
    phrase = client.get("/api/phrases/random").json()
    wav_bytes = make_synthetic_wav()

    res = client.post(
        "/api/attempts/",
        data={"phrase_id": str(phrase["id"])},
        files={"audio": ("recording.wav", wav_bytes, "audio/wav")},
    )
    assert res.status_code == 200
    result = res.json()

    assert result["phrase_id"] == phrase["id"]
    assert 0 <= result["score"] <= 100
    expected_word_count = len([w for w in phrase["text"].split() if w.strip()])
    non_extra = [w for w in result["word_feedback"] if w["status"] != "extra"]
    assert len(non_extra) == expected_word_count


def test_submit_attempt_unknown_phrase_404(client):
    wav_bytes = make_synthetic_wav()
    res = client.post(
        "/api/attempts/",
        data={"phrase_id": "999999"},
        files={"audio": ("recording.wav", wav_bytes, "audio/wav")},
    )
    assert res.status_code == 404


def test_history_and_stats_after_submission(client):
    phrase = client.get("/api/phrases/random").json()
    wav_bytes = make_synthetic_wav()
    client.post(
        "/api/attempts/",
        data={"phrase_id": str(phrase["id"])},
        files={"audio": ("recording.wav", wav_bytes, "audio/wav")},
    )

    history_res = client.get("/api/attempts/", params={"limit": 20})
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) >= 1
    assert {
        "id",
        "phrase_id",
        "phrase_text",
        "transcript",
        "score",
        "word_feedback",
    } <= history[0].keys()

    stats_res = client.get("/api/attempts/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_attempts"] >= 1
    assert stats["average_score"] is not None
    assert len(stats["per_phrase"]) >= 1

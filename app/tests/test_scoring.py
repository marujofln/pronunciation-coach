from app.scoring import align_words, phoneme_edit_distance, score_attempt

FAKE_PHONEMES = {
    "hello": ["HH", "AH", "L", "OW"],
    "world": ["W", "ER", "L", "D"],
    "good": ["G", "UH", "D"],
    "morning": ["M", "AO", "R", "N", "IH", "NG"],
    "today": ["T", "AH", "D", "EY"],
    "sir": ["S", "ER"],
    "think": ["TH", "IH", "NG", "K"],
    "sink": ["S", "IH", "NG", "K"],
    "about": ["AH", "B", "AW", "T"],
    "it": ["IH", "T"],
}


class FakeG2p:
    def __call__(self, word):
        return FAKE_PHONEMES.get(word.lower(), ["X", "X"])


def test_identical_text_scores_100():
    g2p = FakeG2p()
    score, feedback = score_attempt("hello world", "hello world", g2p)
    assert score == 100.0
    assert all(f.status == "correct" for f in feedback)


def test_one_substituted_phoneme_reduces_score_proportionally():
    g2p = FakeG2p()
    score, feedback = score_attempt("think about it", "sink about it", g2p)
    assert feedback[0].expected_word == "think"
    assert feedback[0].heard_word == "sink"
    assert feedback[0].status == "mispronounced"
    # 1 substitution out of 4 phonemes -> word_score 0.75
    assert feedback[0].word_score == 0.75
    assert feedback[1].status == "correct"
    assert feedback[2].status == "correct"
    assert 0 < score < 100


def test_dropped_word_marked_missing():
    g2p = FakeG2p()
    _score, feedback = score_attempt("good morning today", "good today", g2p)
    statuses = [f.status for f in feedback]
    assert "missing" in statuses
    missing = next(f for f in feedback if f.status == "missing")
    assert missing.expected_word == "morning"
    assert missing.word_score == 0.0


def test_extra_word_does_not_lower_score():
    g2p = FakeG2p()
    score, feedback = score_attempt("good morning", "good morning sir", g2p)
    extra = [f for f in feedback if f.status == "extra"]
    assert len(extra) == 1
    assert extra[0].heard_word == "sir"
    assert extra[0].word_score is None
    assert score == 100.0


def test_empty_transcript_scores_zero():
    g2p = FakeG2p()
    score, feedback = score_attempt("hello world", "", g2p)
    assert score == 0.0
    assert all(f.status == "missing" for f in feedback)


def test_phoneme_edit_distance():
    assert phoneme_edit_distance(["A", "B", "C"], ["A", "B", "C"]) == 0
    assert phoneme_edit_distance(["A", "B", "C"], ["A", "X", "C"]) == 1
    assert phoneme_edit_distance(["A", "B"], ["A", "B", "C"]) == 1
    assert phoneme_edit_distance([], []) == 0


def test_align_words_equal_length():
    pairs = align_words(["a", "b", "c"], ["a", "b", "c"])
    assert pairs == [("a", "a"), ("b", "b"), ("c", "c")]


def test_real_g2p_strips_stress_digits(g2p):
    from app.scoring import word_to_phonemes

    phonemes = word_to_phonemes("hello", g2p)
    assert phonemes == ["HH", "AH", "L", "OW"]
    assert all(not any(ch.isdigit() for ch in p) for p in phonemes)


def test_real_g2p_matches_identical_words(g2p):
    score, feedback = score_attempt("hello there", "hello there", g2p)
    assert score == 100.0
    assert all(f.status == "correct" for f in feedback)

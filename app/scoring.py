import re
from difflib import SequenceMatcher

from app.schemas import WordFeedback

WORD_RE = re.compile(r"[a-zA-Z']+")


def normalize_words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def strip_stress(phoneme: str) -> str:
    return re.sub(r"\d", "", phoneme)


def word_to_phonemes(word: str, g2p) -> list[str]:
    return [strip_stress(p) for p in g2p(word) if p.strip()]


def phoneme_edit_distance(a: list[str], b: list[str]) -> int:
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, m + 1):
            cur = dp[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = cur
    return dp[m]


def align_words(
    ref_words: list[str], hyp_words: list[str]
) -> list[tuple[str | None, str | None]]:
    sm = SequenceMatcher(None, ref_words, hyp_words, autojunk=False)
    pairs: list[tuple[str | None, str | None]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            pairs.extend(zip(ref_words[i1:i2], hyp_words[j1:j2]))
        elif tag == "replace":
            ref_seg, hyp_seg = ref_words[i1:i2], hyp_words[j1:j2]
            n = min(len(ref_seg), len(hyp_seg))
            pairs.extend(zip(ref_seg[:n], hyp_seg[:n]))
            pairs.extend((w, None) for w in ref_seg[n:])
            pairs.extend((None, w) for w in hyp_seg[n:])
        elif tag == "delete":
            pairs.extend((w, None) for w in ref_words[i1:i2])
        elif tag == "insert":
            pairs.extend((None, w) for w in hyp_words[j1:j2])
    return pairs


def score_word_pair(
    ref_word: str | None, hyp_word: str | None, g2p, position: int
) -> WordFeedback:
    if ref_word is None:
        heard = word_to_phonemes(hyp_word, g2p)
        return WordFeedback(
            position=position,
            expected_word=None,
            heard_word=hyp_word,
            expected_phonemes=[],
            heard_phonemes=heard,
            status="extra",
            word_score=None,
        )

    expected = word_to_phonemes(ref_word, g2p)

    if hyp_word is None:
        return WordFeedback(
            position=position,
            expected_word=ref_word,
            heard_word=None,
            expected_phonemes=expected,
            heard_phonemes=[],
            status="missing",
            word_score=0.0,
        )

    heard = word_to_phonemes(hyp_word, g2p)
    if expected == heard:
        return WordFeedback(
            position=position,
            expected_word=ref_word,
            heard_word=hyp_word,
            expected_phonemes=expected,
            heard_phonemes=heard,
            status="correct",
            word_score=1.0,
        )

    dist = phoneme_edit_distance(expected, heard)
    denom = max(len(expected), len(heard), 1)
    word_score = max(0.0, 1 - dist / denom)
    return WordFeedback(
        position=position,
        expected_word=ref_word,
        heard_word=hyp_word,
        expected_phonemes=expected,
        heard_phonemes=heard,
        status="mispronounced",
        word_score=round(word_score, 3),
    )


def score_attempt(
    reference_text: str, hypothesis_text: str, g2p
) -> tuple[float, list[WordFeedback]]:
    ref_words = normalize_words(reference_text)
    hyp_words = normalize_words(hypothesis_text)
    pairs = align_words(ref_words, hyp_words)
    feedback = [score_word_pair(r, h, g2p, i) for i, (r, h) in enumerate(pairs)]
    scored = [f.word_score for f in feedback if f.status != "extra"]
    overall = round(100 * sum(scored) / len(scored), 1) if scored else 0.0
    return overall, feedback

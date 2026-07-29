"""Browser tests for frontend/app.js.

These drive a real headless Chromium against the real shipped frontend files,
with every /api/* call intercepted (see the ApiMock fixture in conftest.py).
The FastAPI app is never started here, so no Whisper/G2p model is ever loaded.
"""

import json
import re

import pytest
from playwright.sync_api import Page, expect

from app.tests.conftest import (
    DEFAULT_CATEGORIES,
    DEFAULT_PHRASE,
    ApiMock,
    json_error,
    malformed_json,
    network_error,
)

pytestmark = pytest.mark.frontend

# app.js writes an en dash as the placeholder for an empty phoneme list.
EN_DASH = "–"

PREFS_KEY = "pronunciation-coach:preferences"


def open_app(page: Page, frontend_server: str) -> None:
    page.goto(frontend_server)


def seed_preferences(page: Page, raw: str) -> None:
    """Put a stored preferences value in place before app.js ever runs.

    An init script rather than goto/set/reload, so the page still loads exactly
    once and the "the *first* phrase request already carries the filters"
    assertions keep their meaning. The try/catch is required: the script also
    runs on about:blank, where touching localStorage throws.
    """
    page.add_init_script(
        f"try {{ localStorage.setItem({json.dumps(PREFS_KEY)}, {json.dumps(raw)}) }}"
        " catch (e) {}"
    )


def stored_preferences(page: Page) -> str | None:
    return page.evaluate(f"localStorage.getItem({json.dumps(PREFS_KEY)})")


def record_clip(page: Page) -> None:
    """Drive the record button through a full start/stop cycle.

    Chromium runs with --use-fake-device-for-media-stream, so this exercises
    the genuine getUserMedia + MediaRecorder path rather than a stub.
    """
    page.click("#record-btn")
    expect(page.locator("#record-btn")).to_have_text("■ Stop")
    page.wait_for_timeout(300)  # let the fake mic produce some audio
    page.click("#record-btn")
    expect(page.locator("#submit-btn")).to_be_enabled()


def test_renders_random_phrase(page: Page, frontend_server: str, api: ApiMock):
    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#phrase-difficulty")).to_have_text("hard")
    expect(page.locator("#phrase-category")).to_have_text("Tongue twisters")
    expect(page.locator("#phrase-category")).to_be_visible()


def test_category_badge_hidden_when_phrase_has_no_category(
    page: Page, frontend_server: str, api: ApiMock
):
    api.phrase = {**DEFAULT_PHRASE, "category": None}
    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#phrase-category")).to_be_hidden()


def test_difficulty_select_refetches_with_query_param(
    page: Page, frontend_server: str, api: ApiMock
):
    phrases = [
        dict(DEFAULT_PHRASE),
        {**DEFAULT_PHRASE, "id": 8, "text": "Wristwatch", "difficulty": "easy"},
    ]
    api.phrase = lambda request: phrases.pop(0)

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])

    page.select_option("#difficulty-select", "hard")

    expect(page.locator("#phrase-text")).to_have_text("Wristwatch")
    requests = api.requests_to("/api/phrases/random")
    assert len(requests) == 2
    assert "difficulty=" not in requests[0].url
    assert "difficulty=hard" in requests[1].url


# --- preferences / loadPreferences + savePreferences ---------------------


def test_category_select_is_populated_from_the_api(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)

    options = page.locator("#category-select option")
    expect(options).to_have_count(len(DEFAULT_CATEGORIES) + 1)  # + the "Any" option
    assert options.first.get_attribute("value") == ""
    expect(page.locator("#category-select")).to_have_value("")


def test_category_labels_are_prettified_but_values_stay_slugs(
    page: Page, frontend_server: str, api: ApiMock
):
    """The slug is what the API filters on; only the visible label is cleaned up."""
    open_app(page, frontend_server)

    option = page.locator("#category-select option[value='information-technology']")
    expect(option).to_have_text("Information technology")


def test_saved_preferences_are_restored_on_load(
    page: Page, frontend_server: str, api: ApiMock
):
    seed_preferences(page, json.dumps({"difficulty": "easy", "category": "food"}))

    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#difficulty-select")).to_have_value("easy")
    expect(page.locator("#category-select")).to_have_value("food")

    # The whole point: the first phrase already respects the restored filters,
    # rather than being fetched unfiltered and then replaced.
    requests = api.requests_to("/api/phrases/random")
    assert len(requests) == 1
    assert "difficulty=easy" in requests[0].url
    assert "category=food" in requests[0].url


def test_selecting_a_filter_persists_it(page: Page, frontend_server: str, api: ApiMock):
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])

    page.select_option("#difficulty-select", "hard")
    page.select_option("#category-select", "greetings")

    assert json.loads(stored_preferences(page)) == {
        "difficulty": "hard",
        "category": "greetings",
    }


def test_saved_category_no_longer_offered_is_ignored(
    page: Page, frontend_server: str, api: ApiMock
):
    """A category can disappear from the phrase table; don't select nothing."""
    seed_preferences(
        page, json.dumps({"difficulty": None, "category": "retired-category"})
    )

    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#category-select")).to_have_value("")
    assert "category=" not in api.requests_to("/api/phrases/random")[0].url


def test_corrupt_stored_preferences_fall_back_to_no_filters(
    page: Page, frontend_server: str, api: ApiMock
):
    """The failure mode the try/catch around JSON.parse exists for."""
    seed_preferences(page, "{not json")

    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#difficulty-select")).to_have_value("")
    expect(page.locator("#category-select")).to_have_value("")


def test_unreadable_categories_fall_back_to_no_filters(
    page: Page, frontend_server: str, api: ApiMock
):
    api.categories = json_error(500)

    open_app(page, frontend_server)

    # A failed category load must not stop the app from loading a phrase.
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#difficulty-select")).to_have_value("")
    expect(page.locator("#category-select")).to_have_value("")


def test_new_phrase_button_refetches(page: Page, frontend_server: str, api: ApiMock):
    phrases = [
        dict(DEFAULT_PHRASE),
        {**DEFAULT_PHRASE, "id": 9, "text": "Unique New York"},
    ]
    api.phrase = lambda request: phrases.pop(0)

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])

    page.click("#new-phrase-btn")

    expect(page.locator("#phrase-text")).to_have_text("Unique New York")
    assert len(api.requests_to("/api/phrases/random")) == 2


def test_phrase_load_failure_shows_message(
    page: Page, frontend_server: str, api: ApiMock
):
    api.phrase = json_error(404)
    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text("Could not load a phrase.")
    expect(page.locator("#status-line")).to_have_text("No phrase found (404)")


# --- recording / startRecording + stopRecording + toggleRecording --------


def test_record_button_toggles_state(page: Page, frontend_server: str, api: ApiMock):
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])

    page.click("#record-btn")
    expect(page.locator("#record-btn")).to_have_text("■ Stop")
    expect(page.locator("#record-btn")).to_have_class(re.compile(r"\brecording\b"))
    expect(page.locator("#status-line")).to_have_text(
        "Recording… speak the phrase above."
    )

    page.click("#record-btn")
    expect(page.locator("#record-btn")).to_have_text("● Record")
    expect(page.locator("#record-btn")).not_to_have_class(re.compile(r"\brecording\b"))
    expect(page.locator("#status-line")).to_have_text(
        "Recording captured. Review it, then submit."
    )


def test_stopping_enables_submit_and_sets_preview(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)
    expect(page.locator("#submit-btn")).to_be_disabled()

    record_clip(page)

    # onstop fires asynchronously; to_have_attribute retries until it lands.
    expect(page.locator("#preview")).to_have_attribute("src", re.compile(r"^blob:"))


def test_microphone_denied_shows_permission_message(
    page: Page, frontend_server: str, api: ApiMock
):
    page.add_init_script(
        """
        Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
          configurable: true,
          value: () => Promise.reject(
            new DOMException('Permission denied', 'NotAllowedError')
          ),
        });
        """
    )
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])

    page.click("#record-btn")

    expect(page.locator("#status-line")).to_contain_text("Microphone access failed")
    expect(page.locator("#status-line")).to_contain_text("Check browser permissions")
    expect(page.locator("#submit-btn")).to_be_disabled()


# --- submit / submitAttempt + renderFeedback -----------------------------


def test_submit_posts_phrase_id_and_audio(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    record_clip(page)

    page.click("#submit-btn")
    expect(page.locator("#results-card")).to_be_visible()

    posts = [r for r in api.requests_to("/api/attempts/") if r.method == "POST"]
    assert len(posts) == 1
    body = posts[0].post_data
    assert body is not None
    assert b'name="phrase_id"' in body
    assert b"7" in body
    assert b'filename="recording.webm"' in body


def test_renders_word_feedback(page: Page, frontend_server: str, api: ApiMock):
    api.result = {
        **api.result,
        "score": 87.5,
        "transcript": "she sells sea shells",
        "word_feedback": [
            {
                "position": 0,
                "expected_word": "she",
                "heard_word": "she",
                "expected_phonemes": ["SH", "IY"],
                "heard_phonemes": ["SH", "IY"],
                "status": "correct",
                "word_score": 1.0,
            },
            {
                "position": 1,
                "expected_word": "sells",
                "heard_word": "cells",
                "expected_phonemes": ["S", "EH", "L", "Z"],
                "heard_phonemes": ["S", "EH", "L", "Z"],
                "status": "mispronounced",
                "word_score": 0.5,
            },
            {
                "position": 2,
                "expected_word": "seashells",
                "heard_word": None,
                "expected_phonemes": ["S", "IY"],
                "heard_phonemes": [],
                "status": "missing",
                "word_score": 0.0,
            },
            {
                "position": 3,
                "expected_word": None,
                "heard_word": "shells",
                "expected_phonemes": [],
                "heard_phonemes": ["SH", "EH", "L", "Z"],
                "status": "extra",
                "word_score": None,
            },
        ],
    }

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    record_clip(page)
    page.click("#submit-btn")

    expect(page.locator("#results-card")).to_be_visible()
    expect(page.locator("#overall-score")).to_have_text("87.5/100")
    expect(page.locator("#transcript-text")).to_have_text("she sells sea shells")

    words = page.locator("#feedback-words span")
    expect(words).to_have_count(4)
    expect(words).to_have_text(["she", "sells", "seashells", "shells"])
    for index, status in enumerate(["correct", "mispronounced", "missing", "extra"]):
        expect(words.nth(index)).to_have_class(f"word {status}")

    expect(words.nth(0)).to_have_attribute("title", "expected: SH IY | heard: SH IY")
    expect(words.nth(2)).to_have_attribute(
        "title", f"expected: S IY | heard: {EN_DASH}"
    )
    expect(words.nth(3)).to_have_attribute(
        "title", f"expected: {EN_DASH} | heard: SH EH L Z"
    )

    expect(page.locator("#status-line")).to_have_text(
        "Done. Record again to try another take."
    )


def test_word_with_no_expected_or_heard_word_renders_question_mark(
    page: Page, frontend_server: str, api: ApiMock
):
    api.result = {
        **api.result,
        "word_feedback": [
            {
                "position": 0,
                "expected_word": None,
                "heard_word": None,
                "expected_phonemes": [],
                "heard_phonemes": [],
                "status": "missing",
                "word_score": None,
            }
        ],
    }

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    record_clip(page)
    page.click("#submit-btn")

    expect(page.locator("#feedback-words span")).to_have_text("?")
    expect(page.locator("#feedback-words span")).to_have_attribute(
        "title", f"expected: {EN_DASH} | heard: {EN_DASH}"
    )


def test_empty_transcript_shows_placeholder(
    page: Page, frontend_server: str, api: ApiMock
):
    api.result = {**api.result, "transcript": ""}

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    record_clip(page)
    page.click("#submit-btn")

    expect(page.locator("#transcript-text")).to_have_text("(nothing recognized)")


def test_submit_failure_reenables_button(
    page: Page, frontend_server: str, api: ApiMock
):
    api.result = json_error(500)

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    record_clip(page)
    page.click("#submit-btn")

    expect(page.locator("#status-line")).to_have_text("Scoring failed (500)")
    expect(page.locator("#submit-btn")).to_be_enabled()
    expect(page.locator("#results-card")).to_be_hidden()


def test_submit_refreshes_history_and_stats(
    page: Page, frontend_server: str, api: ApiMock
):
    api.attempts = [
        {
            "id": 1,
            "phrase_id": 7,
            "phrase_text": DEFAULT_PHRASE["text"],
            "transcript": "she sells seashells",
            "score": 91.0,
            "word_feedback": [],
            "created_at": "2026-01-01T00:00:00",
        }
    ]
    api.stats = {"total_attempts": 1, "average_score": 91.0, "per_phrase": []}

    open_app(page, frontend_server)
    expect(page.locator("#history-list li")).to_have_count(1)
    before_history = len(api.requests_to("/api/attempts/"))
    before_stats = len(api.requests_to("/api/attempts/stats"))

    record_clip(page)
    page.click("#submit-btn")
    expect(page.locator("#results-card")).to_be_visible()

    # one extra POST plus one refetch of each of history and stats
    expect(page.locator("#stats-summary")).to_contain_text("1 attempt(s)")
    assert len(api.requests_to("/api/attempts/")) == before_history + 2
    assert len(api.requests_to("/api/attempts/stats")) == before_stats + 1


# --- speech synthesis / speak + hover-to-listen --------------------------


def stub_speech(page: Page) -> None:
    """Replace the Web Speech API with a recorder, before any navigation.

    Headless Chromium ships speechSynthesis but no voices, so the real API
    accepts an utterance and silently does nothing observable. Swapping the
    whole thing out is what makes the calls assertable.
    """
    page.add_init_script(
        """
        window.__tts = { spoken: [], langs: [], cancels: 0 };
        // SpeechSynthesisUtterance is deliberately left real, so the tests
        // exercise the genuine constructor and the lang assignment.
        Object.defineProperty(window, 'speechSynthesis', {
          configurable: true,
          value: {
            speak: (u) => {
              window.__tts.spoken.push(u.text);
              window.__tts.langs.push(u.lang);
            },
            cancel: () => { window.__tts.cancels += 1; },
          },
        });
        """
    )


def tts(page: Page) -> dict:
    return page.evaluate("window.__tts")


def render_feedback(page: Page) -> None:
    """Drive a full record → submit cycle so the feedback words exist."""
    record_clip(page)
    page.click("#submit-btn")
    expect(page.locator("#results-card")).to_be_visible()


# The two-word result the hover tests drive; short enough to hover precisely.
TWO_WORD_RESULT = {
    "score": 50.0,
    "transcript": "she sells",
    "word_feedback": [
        {
            "position": 0,
            "expected_word": "she",
            "heard_word": "she",
            "expected_phonemes": ["SH", "IY"],
            "heard_phonemes": ["SH", "IY"],
            "status": "correct",
            "word_score": 1.0,
        },
        {
            "position": 1,
            "expected_word": "seashells",
            "heard_word": None,
            "expected_phonemes": ["S", "IY"],
            "heard_phonemes": [],
            "status": "missing",
            "word_score": 0.0,
        },
    ],
}


def test_speak_button_speaks_the_current_phrase(
    page: Page, frontend_server: str, api: ApiMock
):
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])

    page.click("#speak-btn")

    recorded = tts(page)
    assert recorded["spoken"] == [DEFAULT_PHRASE["text"]]
    assert recorded["langs"] == ["en-US"]


def test_speak_button_is_disabled_until_a_phrase_loads(
    page: Page, frontend_server: str, api: ApiMock
):
    """Nothing to say before a phrase lands — and nothing stale to say after
    one fails to, which would speak a phrase that isn't on screen."""
    api.phrase = json_error(404)
    stub_speech(page)
    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text("Could not load a phrase.")
    expect(page.locator("#speak-btn")).to_be_disabled()


def test_speak_button_is_disabled_while_recording(
    page: Page, frontend_server: str, api: ApiMock
):
    """Playback out the speakers feeds back into the mic and corrupts the
    very audio about to be scored."""
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#speak-btn")).to_be_enabled()

    page.click("#record-btn")
    expect(page.locator("#record-btn")).to_have_text("■ Stop")
    expect(page.locator("#speak-btn")).to_be_disabled()

    page.wait_for_timeout(300)
    page.click("#record-btn")

    expect(page.locator("#speak-btn")).to_be_enabled()


def test_hovering_a_word_while_recording_stays_silent(
    page: Page, frontend_server: str, api: ApiMock
):
    """A disabled button doesn't stop hover, so speak() guards too."""
    api.result = {**api.result, **TWO_WORD_RESULT}
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    page.click("#record-btn")
    expect(page.locator("#record-btn")).to_have_text("■ Stop")
    page.hover("#feedback-words span:nth-of-type(1)")
    page.wait_for_timeout(900)

    assert tts(page)["spoken"] == []


def test_rerendering_feedback_cancels_a_pending_hover(
    page: Page, frontend_server: str, api: ApiMock
):
    """renderFeedback destroys the spans; the timer must not outlive them.

    Driven directly rather than through a second record/submit cycle, because
    startRecording() also stops speech — going the long way round would pass
    on that guard instead of this one. The pointer stays put over the rebuilt
    span, which legitimately re-arms the hover, so what this pins down is that
    the word spoken is the *new* one and never the discarded one.
    """
    api.result = {**api.result, **TWO_WORD_RESULT}
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    page.hover("#feedback-words span:nth-of-type(1)")
    page.wait_for_timeout(200)
    replacement = {**api.result, **TWO_WORD_RESULT}
    replacement["word_feedback"] = [
        {**replacement["word_feedback"][0], "expected_word": "afterwards"},
        *replacement["word_feedback"][1:],
    ]
    page.evaluate("result => renderFeedback(result)", replacement)
    page.wait_for_timeout(900)

    assert "she" not in tts(page)["spoken"]


def test_repeated_speak_clicks_cancel_the_previous_utterance(
    page: Page, frontend_server: str, api: ApiMock
):
    """Without the leading cancel(), a second click queues behind the first."""
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])

    # renderPhrase() cancels once on load (its stale-timer guard); zero the
    # counter so this asserts about the clicks alone.
    page.evaluate("window.__tts.cancels = 0")

    page.click("#speak-btn")
    page.click("#speak-btn")

    recorded = tts(page)
    assert recorded["spoken"] == [DEFAULT_PHRASE["text"]] * 2
    assert recorded["cancels"] == 2  # one before each speak


def test_hovering_a_feedback_word_speaks_it_after_the_delay(
    page: Page, frontend_server: str, api: ApiMock
):
    api.result = {**api.result, **TWO_WORD_RESULT}
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    page.hover("#feedback-words span:nth-of-type(1)")
    assert tts(page)["spoken"] == []  # nothing yet — the delay hasn't elapsed

    page.wait_for_timeout(900)

    assert tts(page)["spoken"] == ["she"]


def test_brief_hover_over_a_feedback_word_speaks_nothing(
    page: Page, frontend_server: str, api: ApiMock
):
    """The whole point of the delay: incidental mouse travel stays silent."""
    api.result = {**api.result, **TWO_WORD_RESULT}
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    page.hover("#feedback-words span:nth-of-type(1)")
    page.wait_for_timeout(200)
    page.hover("#overall-score")  # leave the word well before the delay
    page.wait_for_timeout(900)

    assert tts(page)["spoken"] == []


def test_hovering_across_words_speaks_only_the_last_one(
    page: Page, frontend_server: str, api: ApiMock
):
    api.result = {**api.result, **TWO_WORD_RESULT}
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    page.hover("#feedback-words span:nth-of-type(1)")
    page.wait_for_timeout(200)
    page.hover("#feedback-words span:nth-of-type(2)")
    page.wait_for_timeout(900)

    # The missing word speaks its expected_word — what should have been said.
    assert tts(page)["spoken"] == ["seashells"]


def test_clicking_a_feedback_word_speaks_it_immediately(
    page: Page, frontend_server: str, api: ApiMock
):
    """Click is the touch/keyboard-reachable path; it skips the hover delay."""
    api.result = {**api.result, **TWO_WORD_RESULT}
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    page.click("#feedback-words span:nth-of-type(2)")

    assert tts(page)["spoken"] == ["seashells"]


def test_unpronounceable_word_is_not_speakable(
    page: Page, frontend_server: str, api: ApiMock
):
    """A word with neither expected nor heard text renders "?" — don't say it."""
    api.result = {
        **api.result,
        "word_feedback": [
            {
                "position": 0,
                "expected_word": None,
                "heard_word": None,
                "expected_phonemes": [],
                "heard_phonemes": [],
                "status": "missing",
                "word_score": None,
            }
        ],
    }
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    word = page.locator("#feedback-words span")
    expect(word).to_have_text("?")
    assert word.get_attribute("data-speak") is None

    word.click()
    word.hover()
    page.wait_for_timeout(900)

    assert tts(page)["spoken"] == []


def test_a_new_phrase_cancels_a_pending_hover(
    page: Page, frontend_server: str, api: ApiMock
):
    """The timer must not outlive the feedback card it was about to read."""
    api.result = {**api.result, **TWO_WORD_RESULT}
    stub_speech(page)
    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    render_feedback(page)

    page.hover("#feedback-words span:nth-of-type(1)")
    page.wait_for_timeout(200)
    page.click("#new-phrase-btn")
    page.wait_for_timeout(900)

    assert tts(page)["spoken"] == []


def test_missing_speech_synthesis_degrades_silently(
    page: Page, frontend_server: str, api: ApiMock
):
    """Not every browser has the Web Speech API; absence must not throw."""
    api.result = {**api.result, **TWO_WORD_RESULT}
    page.add_init_script(
        """
        delete window.SpeechSynthesisUtterance;
        Object.defineProperty(window, 'speechSynthesis', {
          configurable: true, value: undefined,
        });
        """
    )
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    page.click("#speak-btn")
    render_feedback(page)

    page.hover("#feedback-words span:nth-of-type(1)")
    page.wait_for_timeout(900)
    page.click("#feedback-words span:nth-of-type(1)")

    assert errors == []


# --- history / loadHistory -----------------------------------------------


def test_history_empty_state(page: Page, frontend_server: str, api: ApiMock):
    open_app(page, frontend_server)

    expect(page.locator("#history-list li")).to_have_text("No attempts yet.")


def test_history_lists_attempts(page: Page, frontend_server: str, api: ApiMock):
    api.attempts = [
        {
            "id": 2,
            "phrase_id": 7,
            "phrase_text": "Red lorry, yellow lorry",
            "transcript": "red lorry yellow lorry",
            "score": 78.0,
            "word_feedback": [],
            "created_at": "2026-01-02T00:00:00",
        },
        {
            "id": 1,
            "phrase_id": 8,
            "phrase_text": "Unique New York",
            "transcript": "unique new york",
            "score": 95.5,
            "word_feedback": [],
            "created_at": "2026-01-01T00:00:00",
        },
    ]

    open_app(page, frontend_server)

    expect(page.locator("#history-list li")).to_have_count(2)
    expect(page.locator("#history-list .history-phrase")).to_have_text(
        ["Red lorry, yellow lorry", "Unique New York"]
    )
    expect(page.locator("#history-list .history-score")).to_have_text(
        ["78/100", "95.5/100"]
    )
    assert "limit=20" in api.requests_to("/api/attempts/")[0].url


def test_history_error_fallback(page: Page, frontend_server: str, api: ApiMock):
    # Must be a failed request, not a 500: loadHistory has no res.ok check, so
    # only a rejected fetch (or unparseable body) reaches its catch block.
    api.attempts = network_error()
    open_app(page, frontend_server)

    expect(page.locator("#history-list li")).to_have_text("Could not load history.")


def test_history_error_fallback_on_malformed_json(
    page: Page, frontend_server: str, api: ApiMock
):
    api.attempts = malformed_json()
    open_app(page, frontend_server)

    expect(page.locator("#history-list li")).to_have_text("Could not load history.")


# --- stats / loadStats ---------------------------------------------------


def test_stats_empty_state(page: Page, frontend_server: str, api: ApiMock):
    open_app(page, frontend_server)

    expect(page.locator("#stats-summary")).to_have_text("No attempts yet.")


def test_stats_summary(page: Page, frontend_server: str, api: ApiMock):
    api.stats = {"total_attempts": 3, "average_score": 82.4, "per_phrase": []}
    open_app(page, frontend_server)

    expect(page.locator("#stats-summary")).to_have_text(
        "3 attempt(s) so far — average score 82.4/100."
    )


def test_stats_error_fallback(page: Page, frontend_server: str, api: ApiMock):
    api.stats = network_error()
    open_app(page, frontend_server)

    expect(page.locator("#stats-summary")).to_have_text("Could not load stats.")


def test_no_uncaught_page_errors_on_load(
    page: Page, frontend_server: str, api: ApiMock
):
    """A renamed element id in index.html makes els.X null and throws here."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    open_app(page, frontend_server)
    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#stats-summary")).not_to_be_empty()

    assert errors == []


def test_serves_stylesheet(page: Page, frontend_server: str, api: ApiMock):
    """Guards against index.html and the served static files drifting apart."""
    response = page.request.get(f"{frontend_server}/style.css")
    assert response.status == 200
    assert "text/css" in response.headers["content-type"]

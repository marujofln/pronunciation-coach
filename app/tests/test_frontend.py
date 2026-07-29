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


def open_app(page: Page, frontend_server: str) -> None:
    page.goto(frontend_server)


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


# --- user menu / loadCurrentUser -----------------------------------------


def test_user_menu_shows_logged_in_user_on_hover(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)
    expect(page.locator("#user-menu")).to_be_visible()

    # The tooltip is always in the DOM; hovering is what makes it opaque.
    page.hover("#user-menu-btn")

    tooltip = page.locator("#user-tooltip")
    expect(tooltip).to_have_text("tester@example.com")
    expect(tooltip).to_have_css("opacity", "1")


def test_user_menu_falls_back_to_user_id(
    page: Page, frontend_server: str, api: ApiMock
):
    api.me = {"id": 42, "email": None}
    open_app(page, frontend_server)

    expect(page.locator("#user-tooltip")).to_have_text("user #42")
    page.click("#user-menu-btn")
    expect(page.locator("#user-dropdown-email")).to_have_text("user #42")


def test_user_menu_hidden_when_me_fails(page: Page, frontend_server: str, api: ApiMock):
    api.me = json_error(401)
    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#user-menu")).to_be_hidden()


def test_user_menu_click_opens_dropdown(page: Page, frontend_server: str, api: ApiMock):
    open_app(page, frontend_server)
    expect(page.locator("#user-dropdown")).to_be_hidden()
    expect(page.locator("#user-menu-btn")).to_have_attribute("aria-expanded", "false")

    page.click("#user-menu-btn")

    expect(page.locator("#user-dropdown")).to_be_visible()
    expect(page.locator("#user-menu-btn")).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#user-dropdown-email")).to_have_text("tester@example.com")
    expect(page.locator("#logout-link")).to_have_text("Logout")
    expect(page.locator("#logout-link")).to_have_attribute("href", "/auth/logout")


def test_user_menu_second_click_closes_dropdown(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)

    page.click("#user-menu-btn")
    expect(page.locator("#user-dropdown")).to_be_visible()

    page.click("#user-menu-btn")

    expect(page.locator("#user-dropdown")).to_be_hidden()
    expect(page.locator("#user-menu-btn")).to_have_attribute("aria-expanded", "false")


def test_user_menu_closes_on_outside_click(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)

    page.click("#user-menu-btn")
    expect(page.locator("#user-dropdown")).to_be_visible()

    page.click("h1")

    expect(page.locator("#user-dropdown")).to_be_hidden()
    expect(page.locator("#user-menu-btn")).to_have_attribute("aria-expanded", "false")


def test_user_menu_closes_on_escape_and_restores_focus(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)

    page.click("#user-menu-btn")
    expect(page.locator("#user-dropdown")).to_be_visible()

    page.keyboard.press("Escape")

    expect(page.locator("#user-dropdown")).to_be_hidden()
    expect(page.locator("#user-menu-btn")).to_be_focused()


def test_arrow_down_opens_menu_and_focuses_logout(
    page: Page, frontend_server: str, api: ApiMock
):
    open_app(page, frontend_server)
    expect(page.locator("#user-menu")).to_be_visible()

    page.focus("#user-menu-btn")
    page.keyboard.press("ArrowDown")

    expect(page.locator("#user-dropdown")).to_be_visible()
    expect(page.locator("#logout-link")).to_be_focused()


def test_logout_link_navigates_to_auth_logout(
    page: Page, frontend_server: str, api: ApiMock
):
    # frontend_server is a bare static server with no /auth/logout route, so
    # stub it here rather than in ApiMock (which only handles /api/*).
    page.route(
        "**/auth/logout",
        lambda route: route.fulfill(
            status=200, content_type="text/html", body="<p>logged out</p>"
        ),
    )

    open_app(page, frontend_server)
    page.click("#user-menu-btn")
    page.click("#logout-link")

    expect(page.locator("p")).to_have_text("logged out")
    assert page.url.endswith("/auth/logout")


# --- phrase / loadRandomPhrase + renderPhrase ----------------------------


def test_renders_random_phrase(page: Page, frontend_server: str, api: ApiMock):
    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#phrase-difficulty")).to_have_text("hard")
    expect(page.locator("#phrase-category")).to_have_text("tongue twister")
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


def test_saved_preferences_are_restored_on_load(
    page: Page, frontend_server: str, api: ApiMock
):
    api.preferences = {"difficulty": "easy", "category": "food"}

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

    saved = api.requests_to("/api/me/preferences")
    puts = [r for r in saved if r.method == "PUT"]
    assert len(puts) == 2
    assert json.loads(puts[0].post_data) == {"difficulty": "hard", "category": None}
    assert json.loads(puts[1].post_data) == {
        "difficulty": "hard",
        "category": "greetings",
    }


def test_saved_category_no_longer_offered_is_ignored(
    page: Page, frontend_server: str, api: ApiMock
):
    """A category can disappear from the phrase table; don't select nothing."""
    api.preferences = {"difficulty": None, "category": "retired-category"}

    open_app(page, frontend_server)

    expect(page.locator("#phrase-text")).to_have_text(DEFAULT_PHRASE["text"])
    expect(page.locator("#category-select")).to_have_value("")
    assert "category=" not in api.requests_to("/api/phrases/random")[0].url


def test_unreadable_preferences_fall_back_to_no_filters(
    page: Page, frontend_server: str, api: ApiMock
):
    api.preferences = json_error(500)
    api.categories = json_error(500)

    open_app(page, frontend_server)

    # A failed preference load must not stop the app from loading a phrase.
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

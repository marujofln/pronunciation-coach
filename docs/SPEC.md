# Pronunciation Coach — Spec & Tasks

This file is the source of truth for requirements and build status. For "how do I run it" see `README.md`; for "how is it built" see `CLAUDE.md`.

## Overview

A local, single-user web app for practicing English pronunciation: pick a phrase, record yourself saying it in the browser, and get phoneme-level feedback on pronunciation accuracy from an open Whisper model plus a grapheme-to-phoneme scoring pipeline.

## Requirements

- Record phrase audio in the browser (`MediaRecorder`) and transcribe it locally with an open Whisper model — no cloud API calls.
- Score pronunciation at the **phoneme level**, not just word-level transcription match: convert both the target phrase and the transcript to phonemes and compare, so mispronunciations Whisper's language model might "autocorrect" past still get caught. Return per-word feedback (correct / mispronounced / missing / extra) with expected vs. heard phonemes.
- Practice phrases come from a seeded database, filterable/selectable by difficulty and category. The category set spans everyday conversation, professional/domain registers (medical, legal, information technology, …), and phonetics-targeted drill sets; slugs are lowercase and hyphenated, since the frontend renders them verbatim as the select's option labels.
- Every attempt (transcript, score, per-word feedback) is persisted, with history and basic stats (average score, per-phrase averages) viewable.
- Frontend is plain HTML/CSS/JS with no build step, served directly by the backend.
- Backend is FastAPI, following the `fastapi` skill's conventions (Annotated dependencies, no Ellipsis defaults, no RootModel, return-type-driven serialization, router-level prefix/tags, SQLModel, uv for dependency management).
- No authentication: the app is single-user and local, and ships that way for the open-source release. An OIDC/Authentik integration was built and then removed — see the "Open-source release" decision below; it is preserved on the `auth-authentik` branch.
- Persist the user's choices (their difficulty/category filter selection) so they carry over between visits — in the browser's `localStorage`, since there is no account to key them to.
- A "speak" button lets the user listen to the correct pronunciation of the target phrase (reference audio, not their own recording).
- Hover-to-listen: hovering over a word for N seconds plays that word's correct pronunciation on its own.
- Runs on CPU only (no GPU dependency).
- Docker is the preferred way to run the app; native `uv` remains supported for development.
- Database: PostgreSQL, not SQLite. Supersedes the original v0.0.1 "SQLite file under `data/`" scope (see Database checklist below).
- Schema changes are managed with Alembic migrations, not `SQLModel.metadata.create_all()`.



## Decisions



### Open-source release: no built-in authentication

The project is being published as open source, which reverses the earlier decision to authenticate users against Authentik. The reasoning that motivated auth — "the app is multi-user now" — was never really true of this app: it is a pronunciation trainer you run on your own laptop against your own microphone. What auth actually bought was a per-account partition of a database only one person ever opens.

What it *cost* is the on-ramp. A contributor cloning the repo had to add a line to `/etc/hosts`, generate four secrets, bring up three Authentik containers, click through an admin UI to mint a client ID and secret, and only then could the app boot at all — because `app/config.py` reads `AUTHENTIK_*`/`SESSION_SECRET_KEY` with no defaults and fails loudly without them. That is a lot of friction in front of "record yourself and see a score", and it is friction that only pays off for a deployment shared with other people.

So the requirement is dropped rather than diluted: no half-measure single-user login, no optional-auth branch in the code. The entire integration (`app/auth.py`, `app/routers/auth.py`, the `User`/`UserPreference` tables, the three Authentik compose services, the blueprint) is **preserved verbatim on the `auth-authentik` branch** and can be revived if this is ever deployed somewhere shared. `POSTGRES_PASSWORD` is now the only required-no-default config.

Three consequences worth recording:

- **Preferences move to the browser.** With no account to key a `UserPreference` row to, the difficulty/category selection lives in `localStorage` under `pronunciation-coach:preferences`. The `GET`/`PUT /api/me/preferences` endpoints and the table are gone. The ordering constraint in `app.js`'s `init()` — categories loaded before preferences applied — survives unchanged, because it was never about the network: a saved category can only be selected once its `<option>` exists.
- **Attempts are global.** `Attempt.user_id` is gone; history and stats query the whole table.
- **The Alembic history was squashed, not extended.** The single initial revision was rewritten in place to describe the auth-free schema, rather than adding a second revision that drops `app_user`. There is no deployed database whose history needed preserving, and a public repo's first migration should describe the schema the code actually has. The cost is that an existing local database must be recreated (`docker compose down -v`); this is documented in README's "Upgrading an existing local install".

### Frontend: stay with vanilla JS, no framework

The feature set is escalating (persisted preferences, TTS playback with a speak button and per-word hover timers, on top of the existing recording/scoring/history/stats UI — at the time this was written, an auth login/logout flow too), which raises the question of whether a frontend framework (React/Vue/Svelte) is now the better choice over plain HTML/CSS/JS.

**Recommendation: stay with vanilla JS.** None of the planned features need component reactivity or complex state trees — TTS playback is a couple of `SpeechSynthesis` calls, hover-to-listen is a `mouseenter`/`mouseleave` timer, and preferences are a `localStorage` read applied to two `<select>`s. All of that fits the state-object-plus-render-functions pattern `app.js` already uses. Adopting a framework would mean a build step and Node tooling, reversing the earlier no-build-step decision, without a matching benefit at this scope. If `app.js` grows unwieldy, split it into small ES modules (e.g. `recording.js`, `playback.js`, `preferences.js`) imported from `index.html` — that gets code organization without a build step. Revisit this if a future requirement introduces genuinely complex client state (multi-step flows, many interdependent views), which nothing currently planned does.

### TTS approach: browser-native Web Speech API

For the speak button and hover-to-listen, use the browser's built-in `SpeechSynthesis` API (`window.speechSynthesis`) rather than a server-side TTS model: it's free, needs no new backend dependency, works with the existing no-cloud-calls / open-source ethos, and is a few lines of JS to wire up. Voice quality/availability depends on the user's OS/browser, which is an acceptable tradeoff for this use case. If voice quality becomes a real problem later, a local neural TTS model (e.g. Piper) is the natural upgrade path — same "open, local, CPU-only" spirit as the existing faster-whisper integration — but isn't warranted to start.

### Database: PostgreSQL via a `docker-compose.yml` service, schema managed by Alembic

Moving off SQLite was driven by the app being multi-user at the time (auth + per-user attempts/preferences): SQLite's single-writer model is a worse fit than Postgres for concurrent authenticated users, and Postgres paired naturally with the auth server, which wanted a Postgres of its own. **That justification lapsed when auth was removed** (see the Open-source release decision above) — but Postgres stays: the migration is done, Alembic is wired to it, several schema choices in `app/models.py` are Postgres-specific, and reverting would be pure churn for a single-user app that is not writing enough to care either way. Run Postgres as a `db` service in `docker-compose.yml` (named volume for data, not a bind mount, since Postgres manages its own on-disk format), and switch `app/db.py`'s `create_engine` call from the `sqlite:///` URL to a `postgresql+psycopg://` URL built from env vars (host/port/db/user/password), following `app/config.py`'s existing pattern of computing config at import time from the environment. `psycopg[binary]` is the driver (actively maintained `psycopg3`, prebuilt wheels, no separate libpq install needed in the container).

Schema changes move from `SQLModel.metadata.create_all()` (implicit, additive-only, fine for a throwaway SQLite file) to explicit Alembic migrations, since Postgres is now a persistent shared service that other services (the auth server) and future deployments depend on — ad hoc `create_all()` can't express column drops/renames or data backfills, which real schema evolution eventually needs. `alembic init` generates `app/alembic/`; `env.py` imports `SQLModel.metadata` (all models must already be imported so their tables are registered) as the autogenerate target and reads the DB URL from `app/config.py` rather than duplicating it in `alembic.ini`. Migrations run explicitly (`uv run alembic upgrade head`), not automatically from app startup, so a bad migration doesn't take the app down on boot — run it as a one-off step in local dev and as an explicit step (or init container) in Docker before the app service starts.

### Practice phrase categories: professional registers + phonetics drills

The seeded categories started out as everyday-conversation topics only — `greetings`, `food`, `travel`, `business`, `small-talk`, `tongue-twisters`, `weather`, `technology`. That under-serves the app's actual user: a working non-native speaker whose hardest pronunciation problems are in the vocabulary of their *job*, not at the coffee shop. Latinate legal terms, Greek-rooted clinical vocabulary, and IT jargon with unstable stress (`ˈdeploy` vs. `deˈployment`) are exactly the words people mispronounce in the meetings that matter, and none of them were reachable. So the taxonomy grows along two axes: **professional/domain registers**, and **phonetics-targeted drill sets** that exercise the scorer itself rather than a topic.

`minimal-pairs` is the most valuable of the drill sets and is worth calling out: `ship`/`sheep`, `think`/`sink`, `rice`/`lice` are precisely the contrasts a transcription-only comparison would miss, because Whisper's language model happily "autocorrects" the wrong one into the contextually plausible one. Scoring at the phoneme level is what this app has that a dictation app doesn't, and a category built out of minimal pairs is the direct exercise of it.

**Terminology —** `legal`**, not** `justice`**.** The lawyers' professional domain and register is *legal* in English ("legal English", "legal counsel", "legal department", "legal advice"). *Justice* names the abstract ideal or the institution (the court system, a Supreme Court Justice), not the field of practice — a category called `justice` would read as a civics topic rather than a vocabulary set for practising lawyers. Hence the slug `legal`.

**Naming convention**: lowercase, hyphenated, no spaces. The slug is the API contract — it's the `?category=` query value and what a `UserPreference` row stores — while `categoryLabel()` in `frontend/app.js` derives the display text from it (sentence case, hyphens to spaces), so nothing needs a hand-maintained slug → label map.

**Full set (20 categories).** Everyday conversation: `greetings`, `small-talk`, `food`, `travel`, `weather`, `tongue-twisters`. Professional/domain registers: `information-technology`, `medical`, `legal`, `finance`, `business`, `education`, `science`, `engineering`, `customer-service`, `job-interview`, `public-speaking`. Phonetics drills: `minimal-pairs`, `numbers-and-dates`, `idioms`.

`technology` **→** `information-technology`: a rename, not an addition. The seven existing `technology` phrases (wifi passwords, software updates) are already IT-flavoured, and shipping both slugs would put two near-identical options next to each other in the dropdown with no principled way for a user to guess which holds what. The scope broadens with the rename, from consumer gadgets to the workplace IT register. One wrinkle: a stored preference may still hold `"technology"`, which then matches no phrase. That degrades safely — `hasOption()` in `frontend/app.js` ignores a saved category that's no longer offered and falls back to "Any".

## Build checklist



### Core app

- [x] Scaffold uv project (`pyproject.toml`, `[tool.fastapi]` entrypoint, runtime + dev dependencies)
- [x] `app/config.py` (env-driven paths, self-contained `data/` dir) and `app/db.py` (SQLModel engine/session)
- [x] `app/models.py` — `Phrase` and `Attempt` SQLModel tables
- [x] `app/schemas.py` — API request/response models (`WordFeedback`, `PhraseRead`, `AttemptRead`, `AttemptResult`, `StatsRead`)
- [x] `app/seed_data.py` — 133 seeded phrases across 20 categories × 3 difficulties, idempotent seeding (see Practice phrase categories below)
- [x] `app/ml.py` — Whisper (`small.en`, CPU, int8) and G2p model loading, once at startup, nltk `<3.9` compatibility fix
- [x] `app/scoring.py` — normalization, per-word G2P, `difflib` word alignment, phoneme edit-distance scoring
- [x] `app/routers/phrases.py` and `app/routers/attempts.py` — all endpoints
- [x] `app/main.py` — lifespan wiring, router registration, `app.frontend()` static mount
- [x] `frontend/` — `index.html`, `app.js` (record/submit/render), `style.css`



### Testing & verification

- [x] `app/tests/` — unit tests for the scoring algorithm (hand-crafted ARPAbet cases) and `TestClient` smoke tests (phrases, attempts, history, stats) with an isolated data dir and synthetic WAV audio
- [x] **Frontend test coverage** — `app/tests/test_frontend.py`, 43 headless-Chromium tests via `pytest-playwright` (marker: `frontend`) driving the real shipped `frontend/` files: phrase loading + difficulty/category filters + failure path, preference restore/persist/fallback against `localStorage`, the full record → stop → submit flow, per-word feedback rendering for all four statuses (correct/mispronounced/missing/extra) including phoneme tooltips, speak-button and hover/click TTS playback, history and stats with their empty/error states. Deliberately does **not** start the FastAPI app — a `ThreadingHTTPServer` serves `frontend/` and an `ApiMock` fixture intercepts every `/api/*` call in the browser, so no Whisper/G2p model is ever loaded (~15s vs. ~40s). Chromium runs with `--use-fake-device-for-media-stream`, so the genuine `getUserMedia` + `MediaRecorder` path is exercised rather than stubbed. Server-side frontend wiring (static assets actually served by FastAPI, `/api/*` not shadowed by the static mount, `/docs` reachable, plus a contract test asserting every `getElementById` in `app.js` has a matching `id` in `index.html`) lives in `app/tests/test_static.py`. One-time setup: `uv run playwright install chromium`.
- [x] Full pytest suite passing (`uv run pytest`) — 69 tests
- [x] Native run verified end-to-end via curl (phrases, random, attempt submission, history, stats)
- [x] **Manual verification in a real browser**: grant mic permission, record real speech, confirm transcription and scoring behave sensibly on both correct and mispronounced attempts — not yet confirmed by the user. Automated tests use synthetic non-speech audio (silence/sine tone), which validates the pipeline mechanically but can't validate transcription/scoring accuracy on real speech.



### Docs & repo

- [x] `CLAUDE.md` — commands and architecture notes for future agent sessions
- [x] `README.md` — features, setup (Docker-first, native alternative), configuration, dev commands, project layout
- [x] `docs/SPEC.md` — this file
- [x] Git repo initialized, pushed to `https://github.com/marcelojcaraujo/pronunciation-coach`



### Docker

- [x] `Dockerfile` (uv + python base image, ffmpeg, layered dependency install, healthcheck)
- [x] `docker-compose.yml` (port mapping, bind-mounted `data/`, `HOST_UID`/`HOST_GID` so container-written files aren't root-owned)
- [x] `.dockerignore`
- [x] Build and full end-to-end verification through the running container (API, frontend, and a submitted attempt all confirmed working)
- [x] `docker-compose.dev.yml` — standalone dev variant with dev-only secrets baked in, so it comes up with no `.env` at all. A full duplicate of `docker-compose.yml` rather than an override layer, with `-dev` volume names and its own Compose project name (without which a `down` here would remove the other file's same-named containers). Publishes Postgres on host port 55432 so a native `uv run fastapi dev` / `uv run alembic` can borrow it. Originally also auto-configured Authentik via a declarative blueprint; removed with the rest of the auth stack.



### Versioning

- [x] Project versioned in `pyproject.toml` / `uv.lock`: `0.0.1` initially, `0.1.0` once authentication and the automated dev stack landed, **`0.2.0`** for the open-source release that removed them again — a headline feature going away is as much a minor bump as one arriving.



### Authentication — removed

Built (Authentik OIDC, `app/auth.py`, `app/routers/auth.py`, `User`/`UserPreference` tables, a top-right user menu with Logout, three Authentik compose services and a declarative blueprint), then **removed for the open-source release** — see the "Open-source release: no built-in authentication" decision above for the reasoning. The complete implementation is preserved on the `auth-authentik` branch; nothing about it is documented further here, since the code no longer exists on this branch to describe.



### User preferences

Originally a `UserPreference` table keyed by authenticated user ID, read and written through `GET`/`PUT /api/me/preferences`. When auth was removed there was no account left to key it to, so storage moved to the browser — the *behaviour* below is unchanged, only where the two values live.

- [x] Persist the user's choice (difficulty/category filter) on selection — `savePreferences()` fires on every `change` of either select in `frontend/app.js`, alongside the existing refetch, writing `{difficulty, category}` to `localStorage` under `pronunciation-coach:preferences`
- [x] Load the saved choice as the default on return, instead of resetting each visit — `init()` in `app.js` loads categories, then preferences, then the first phrase, so the opening phrase already respects the restored filters instead of visibly swapping out. A saved category that's no longer offered is ignored (`hasOption()`) rather than silently selecting nothing
- [x] Degrade rather than fail — both `loadPreferences()` and `savePreferences()` are wrapped in `try`/`catch`: `localStorage` throws outright when storage is blocked (private mode, third-party-cookie policies), and `JSON.parse` throws on a hand-edited or truncated value. Neither should stop a phrase from loading
- [x] Supporting work the feature needed: the frontend had a difficulty select but **no category filter at all**, so a stored category preference would have been unreachable — added a `#category-select` populated by a new `GET /api/phrases/categories` (distinct non-null categories, sorted) and wired into the random-phrase query
- [x] Test coverage — 6 browser tests in `test_frontend.py`: category options populated, labels prettified while values stay slugs, saved filters restored and applied to the *first* phrase request, selection persisted to `localStorage`, stale category ignored, corrupt stored JSON falls back to no filters. Seeded via a `seed_preferences` `add_init_script` helper so the page still loads exactly once and the first-request assertion keeps its meaning



### Practice phrase categories

Twelve new categories plus one rename, taking the seeded set from 8 to 20 and the phrase count from 52 to **133** (see the Decisions entry above for the rationale and the `legal`-vs-`justice` terminology note). Almost purely a data change — `Phrase.category` is a free-form nullable string with no enum or FK, and `GET /api/phrases/categories` derives the dropdown from whatever is in the table.

- [x] **Professional / domain registers** — nine new categories in `app/seed_data.py`:
  - `medical` — symptoms, appointments, prescriptions, diagnoses. Greek/Latin polysyllables, silent letters (`pneumonia`, `psychiatry`), stress that moves under suffixation
  - `legal` — contracts, liability, testimony, jurisdiction, litigation. Latinate vocabulary and long noun phrases (the lawyers' register; see the terminology note in Decisions)
  - `finance` — interest rates, invoices, quarterly results, mortgages. Number-heavy phrasing, `-tion`/`-ial` endings
  - `education` — lectures, assignments, enrolment, grading. Academic register, `-ity`/`-ology` stress patterns
  - `science` — experiments, hypotheses, measurements, lab procedure. Irregular plurals (`hypothesis`/`hypotheses`), technical stress
  - `engineering` — specifications, tolerances, maintenance, materials. Compound-noun stress, consonant clusters
  - `customer-service` — complaints, refunds, apologies, escalation. Polite intonation, modal-heavy sentences
  - `job-interview` — strengths, experience, availability, salary expectations. Self-presentation register
  - `public-speaking` — presentations, transitions, summarising, handling Q&A. Sentence-level prosody and pacing
- [x] **Phonetics drill sets** — three new categories:
  - `minimal-pairs` — `ship`/`sheep`, `bat`/`bad`, `think`/`sink`, `rice`/`lice`, `full`/`fool`. The contrasts the phoneme-level scorer exists to catch and that Whisper's LM is likeliest to autocorrect past
  - `numbers-and-dates` — prices, phone numbers, years, ordinals, times; `thirteen`/`thirty` stress and `-th` endings
  - `idioms` — fixed expressions where connected speech and rhythm matter more than any individual word
- [x] **Rename** `technology` **→** `information-technology` — the 7 existing rows retagged, plus three new workplace-register phrases (deployment, authentication, latency, containerized infrastructure) so the category isn't only consumer gadgets
- [x] **Reconcile existing rows on seed** — the wrinkle the rename exposed: `seed_phrases()` is idempotent *keyed on* `text`, so editing a seeded phrase's category or difficulty never reached an existing `data/pronunciation_coach.db` — it would have shown **both** `technology` and `information-technology` in the dropdown forever. `seed_phrases()` now also updates any existing row whose `(category, difficulty)` drifted from the seed list, making the seed data authoritative for the rows it owns. Stored preferences needed the same treatment at the time: a `rename_technology_preferences()` stopgap, called from `app/main.py`'s lifespan alongside seeding, carried a saved `"technology"` filter across the rename. It was deleted when preferences left the database; a browser still holding the stale slug falls back to "Any" via `hasOption()`
- [x] **Seed ~6 phrases per new category** (2 easy / 2 medium / 2 hard) following the existing `{"text", "difficulty": Difficulty.x, "category"}` dict shape — 133 phrases total, 44 easy / 45 medium / 44 hard. `app/seed_data.py` is now grouped by **category** rather than by difficulty (one `# --- <category> ---` banner each, easy → medium → hard inside): at 20 categories the old difficulty banners scattered each category across three distant blocks and made the coverage rule below impossible to eyeball. Entry order only determines insert order (and therefore `id`) on a fresh DB, and nothing asserts either
- [x] **Give every category at least one phrase at each difficulty**, so no filter combination 404s from `/api/phrases/random`. The three pre-existing gaps are backfilled: `greetings` gained a medium and a hard, `food` a hard, `tongue-twisters` an easy and a medium — `hard`+`greetings`, `hard`+`food` and `easy`+`tongue-twisters` used to return "No phrase matches the given filters"
- [x] **Frontend label prettifying** — `categoryLabel()` in `frontend/app.js` maps hyphens to spaces and applies **sentence** case ("Information technology", "Numbers and dates"), not title case, which would capitalize the joiners ("Numbers And Dates"). Applied to both the select's `option.textContent` and the phrase badge in `renderPhrase()`; `option.value` keeps the raw slug, so the `?category=` query, the stored preference values and `hasOption()` are all untouched
- [x] **Refresh the stale counts** — `README.md` (phrase count + the category list, now grouped by the three themes) and `CLAUDE.md` (count, plus a note on the reconcile behaviour, since "idempotent, keyed off the unique `text` column" was only half the story)
- [x] **Test updates** — `app/tests/test_api.py`'s bound raised to `>= 120`, plus a **coverage-matrix test** asserting all 20 × 3 category/difficulty combinations return 200 (the regression guard that keeps the gap from coming back) and one asserting the rename actually applied. New `app/tests/test_seed_data.py` covers the seed list's internal consistency (unique texts, lowercase-hyphenated slugs, full coverage) and the reconcile path — a retagged phrase is fixed up without inserting a duplicate. In `test_frontend.py`, a new test asserts the prettified label while the option value stays the slug; the Playwright mock's `DEFAULT_CATEGORIES` gained `information-technology` (and `DEFAULT_PHRASE`'s category became the real `tongue-twisters` slug instead of `"tongue twister"`) so the mocks match what the API actually returns



### Audio playback / TTS

Browser-native `SpeechSynthesis` throughout (see the TTS decision above) — no backend change, no new dependency, ~60 lines of `frontend/app.js`.

**Scope: the per-word feedback results, not the phrase display.** The requirement said "in the phrase display and/or the per-word feedback results"; this settles it on the results, where knowing what a word *should* have sounded like is the actual teaching moment. `renderPhrase()` is therefore untouched — the target phrase stays a single `textContent` assignment, and the speak button covers it whole.

- [x] Add a "speak" button next to the target phrase that plays it via the Web Speech API — a round `#speak-btn` in a new `.phrase-row` flex wrapper. Uses the icon-button look rather than the accent fill of `#new-phrase-btn`/`#record-btn`/`#submit-btn`: a fourth solid pill wedged between "New phrase" and "Record" would read as a fourth co-equal CTA and bury the primary path. The shared round-glyph rules moved out of `.user-icon` into a reusable `.icon-btn` that `#user-menu-btn` now also carries
- [x] Add hover-to-listen on individual words with a configurable delay before triggering — `HOVER_SPEAK_DELAY_MS = 700`, delegated `mouseover`/`mouseout` on `#feedback-words` (`mouseenter`/`mouseleave` don't bubble, and `renderFeedback()` rebuilds the spans on every attempt, so per-span wiring would re-register each render). 700ms is also deliberately above Chrome's ~500ms native `title` delay, so a word's phoneme tooltip lands *before* its audio instead of racing it. Speakable words are marked with a **`data-speak` attribute, not a class** — `test_frontend.py` asserts `to_have_class("word {status}")`, which matches the whole class attribute, so an added class would break four assertions. The value is `expected_word || heard_word`: hearing the *correct* pronunciation is the point, so a `missing` word plays what should have been said; an `extra` word has only a heard word and falls back to it. A word with neither renders "?" and is left unmarked
- [x] Cancel/debounce in-flight speech synthesis on rapid hover changes or repeated button clicks — one `stopSpeaking()` clears both halves (the pending timer *and* the in-flight utterance) and is called from **inside `speak()`**, so no entry point has to remember it. The cancel on phrase change lives at the `textContent` wipe in `loadRandomPhrase()`, **not** in `renderPhrase()`: `renderPhrase` only runs after an unbounded `await fetch`, so a hover armed just before "New phrase" would fire during the fetch, and the failure path never reaches `renderPhrase` at all
- [x] **Click-to-speak as well as hover**, beyond the original three bullets: hover doesn't exist on touch devices and isn't keyboard reachable, so per-word playback would have been silently unreachable there. Same delegated handler, no delay. Per-word playback is deliberately *not* given `tabindex` — that would add 6–8 tab stops per phrase for a net accessibility loss; the phrase-level `<button>` is the keyboard path
- [x] **Don't speak into an open microphone** — speaker output feeds straight back into `getUserMedia` on the laptop-plus-built-in-mic setup this app targets, corrupting the very audio about to be scored. `#speak-btn` is disabled while recording (and until the first phrase loads, so it can't speak a phrase that isn't on screen), and `speak()` carries the same guard because a disabled button doesn't stop hover

**Known browser quirk, not worth coding around**: `mouseover` is not an activation-triggering event, and Chrome gates `speechSynthesis` behind user activation. So on a cold page load the very first hover-to-listen can be silent until the user has clicked *something* — which the normal flow (New phrase / Record / the speak button) supplies almost immediately. Invisible to the suite, since the spy never reaches the real engine.



### Database: PostgreSQL + Alembic

- [x] Add `psycopg[binary]` (driver) and `alembic` as `pyproject.toml` dependencies — both **runtime**, not dev: the image is built `--no-dev` and the migrate container runs `alembic upgrade head` inside it. `testcontainers[postgres]` went into the dev group
- [x] Add a `db` (Postgres) service to `docker-compose.yml` with a named volume for data and healthcheck; wire the app service's `depends_on` to it — `pronunciation-coach-db`. It gets **no** `user: ${HOST_UID}` override (the postgres image runs `initdb` as root, then drops privileges; forcing a UID breaks first boot — and a named volume means there's no host-ownership problem to solve). Healthcheck interval is a tight 5s because `up` blocks on it twice over, once for migrate and once for the app
- [x] Add Postgres connection env vars to `app/config.py` (host/port/db/user/password, or a single `DATABASE_URL`), following the existing fail-loudly pattern for required config — both: `DATABASE_URL` overrides wholesale when set, otherwise `POSTGRES_HOST`/`PORT`/`DB`/`USER` (defaulted) + a required-no-default `POSTGRES_PASSWORD`. Built with `URL.create()`, not an f-string, so a password containing `:@/?` is percent-encoded rather than silently corrupting the URL
- [x] Update `app/db.py`'s `create_engine` call to build a `postgresql+psycopg://` URL instead of `sqlite:///` — plus `pool_pre_ping=True` (a Postgres server drops pooled connections; a SQLite file never did) and `-c timezone=utc`. `connect_args={"check_same_thread": False}` had to go; psycopg raises `TypeError` on it
- [x] `alembic init app/alembic`; wire `env.py`'s target metadata to `SQLModel.metadata` and its DB URL to `app/config.py` — `alembic.ini` sits at the repo root (so `uv run alembic` needs no `-c`, and `prepend_sys_path = .` is what lets `env.py` `import app`) and carries **no** `sqlalchemy.url`, keeping the password out of a committed file. `env.py` uses `create_engine()` rather than `engine_from_config()`, since `alembic.ini` is parsed by ConfigParser and a `%` in a password would be read as interpolation syntax
- [x] Generate an initial migration capturing the current schema and verify `alembic upgrade head` produces a schema matching the old `create_all()` output — autogenerated against an empty scratch Postgres, then reviewed against a 9-point checklist; `alembic check` clean, `downgrade base` → `upgrade head` round-trips, `\dT` lists no types. Schema decisions were settled *before* revision 1, since each would otherwise cost a migration later: `Difficulty` as **VARCHAR** via `native_enum=False` (dodges `ALTER TYPE ... ADD VALUE`/`DROP TYPE`, neither of which autogenerate emits), `word_feedback` as **JSONB** (generic `sa.JSON` compiles to PG `json`, which has no `=` operator), all datetimes as **TIMESTAMPTZ** (the values written are aware, and psycopg3's implicit cast into a naive column runs through the session's TimeZone GUC), and — while the auth tables existed — `user` → `app_user`, since `user` is a reserved word and `SELECT * FROM user` is a syntax error. A `naming_convention` on `SQLModel.metadata` lives in `app/__init__.py` — the only module guaranteed to run before `models.py`, since SQLAlchemy resolves constraint names at *attach* time. The revision was later **rewritten in place** rather than superseded when the auth tables were dropped (see the Open-source release decision above)
- [x] Remove/replace the current `SQLModel.metadata.create_all()` startup call in `app/main.py`'s lifespan with an explicit migration step (documented in `README.md`/`CLAUDE.md`), not an automatic one — the lifespan now only seeds. Docker gets a one-shot `pronunciation-coach-migrate` init service (`restart: "no"`, quoted — bare `no` is YAML `false`) that the app `depends_on` with `service_completed_successfully`, sharing the app's image tag so the migration is provably the same code. Seeding deliberately **stays** in the lifespan: it's idempotent, it's data the app owns, and it reconciles drifted rows — freezing 133 phrases into a migration would mean a revision per phrase edit
- [x] Update `app/tests/conftest.py`'s test isolation to spin up (or point at) a Postgres instance per test run instead of a SQLite temp file — `testcontainers` by default, `PRONUNCIATION_COACH_TEST_DATABASE_URL` to point at an existing instance. The trick that keeps it cheap: `create_engine()` doesn't connect, so only the *URL* must exist at import time (where `app/db.py` builds the engine) and the container can start lazily in a session-scoped `database` fixture — the `frontend`-marked tests never request it, so they still run in ~23s with no Docker at all. A `DROP SCHEMA public CASCADE` at session start restores the fresh-database guarantee the tmpdir gave (several tests assert exact row counts), and refuses any database whose name lacks `test`
- [x] Update `CLAUDE.md` (architecture notes, commands) and `README.md` (setup/config) once implemented — plus a new `app/tests/test_migrations.py` running `alembic check`, so model-vs-migration drift fails the suite rather than surfacing as a missing column at runtime. `rename_technology_preferences()` was deleted with **no** replacement data migration: revision 1 *creates* the tables, so no Postgres database could ever hold the stale `"technology"` value, and a migration that provably cannot update a row implies a history that didn't happen



## Open items

- [x] Manual real-microphone pronunciation test in a browser (see Testing & verification above) — the one requirement that still needs a human to confirm.
- [x] Persist user choices between visits (see User preferences checklist above) — done: `localStorage` under `pronunciation-coach:preferences`, with the difficulty + category selects restored on load.
- [x] Remove authentication for the open-source release (see the Open-source release decision and the Authentication section above) — done: `app/auth.py`, `app/routers/auth.py`, `app/routers/preferences.py`, the `User`/`UserPreference` tables, the user menu, the three Authentik compose services and the blueprint are all gone; `POSTGRES_PASSWORD` is the only required-no-default config. Preserved on `auth-authentik`.
- [x] Expand the practice-phrase categories from 8 to 20 — professional registers (medical, legal, information-technology, …) plus phonetics drill sets (see Practice phrase categories checklist above) — done: 133 phrases, every category covering all three difficulties.
- [x] Speak button + hover-to-listen TTS (see Audio playback / TTS checklist above) — done: browser-native `SpeechSynthesis`, a `#speak-btn` for the whole phrase, and hover-or-click playback on the per-word feedback results. Still needs a human ear: headless Chromium has no voices, so the suite only ever exercises a spy.
- [x] Migrate from SQLite to PostgreSQL with Alembic-managed schema (see Database checklist above) — done: `pronunciation-coach-db` service, `postgresql+psycopg://`, one initial migration, `create_all()` gone from the lifespan, and a testcontainers-backed test suite.

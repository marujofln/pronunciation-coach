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
- User authentication: authenticate users against an external authentication server (OAuth2/OIDC) — preferably open-source, easy to integrate with this FastAPI + plain-JS stack, and free of charge. Supersedes the original v0.0.1 "no auth, single local user" scope (see Authentication checklist below).
- Persist each authenticated user's choices (e.g. their difficulty/category filter selection) in the database, tied to their account, so preferences carry over between visits.
- User menu in the frontend: a user icon in the top-right corner of the logged-in screen; hovering it shows the logged-in user; clicking it opens a menu with a "Logout" option that ends the session. Superseded the original inline "Logged in as X · Logout" header text (see User menu checklist below).
- A "speak" button lets the user listen to the correct pronunciation of the target phrase (reference audio, not their own recording).
- Hover-to-listen: hovering over a word for N seconds plays that word's correct pronunciation on its own.
- Runs on CPU only (no GPU dependency).
- Docker is the preferred way to run the app; native `uv` remains supported for development.
- Database: PostgreSQL, not SQLite. Supersedes the original v0.0.1 "SQLite file under `data/`" scope (see Database checklist below).
- Schema changes are managed with Alembic migrations, not `SQLModel.metadata.create_all()`.



## Decisions



### Frontend: stay with vanilla JS, no framework

The feature set is escalating (auth login/logout, persisted preferences, TTS playback with a speak button and per-word hover timers, on top of the existing recording/scoring/history/stats UI), which raises the question of whether a frontend framework (React/Vue/Svelte) is now the better choice over plain HTML/CSS/JS.

**Recommendation: stay with vanilla JS.** None of the planned features need component reactivity or complex state trees — TTS playback is a couple of `SpeechSynthesis` calls, hover-to-listen is a `mouseenter`/`mouseleave` timer, an auth flow is a redirect plus a token check, and preferences are one more field on existing fetch/render calls. All of that fits the state-object-plus-render-functions pattern `app.js` already uses. Adopting a framework would mean a build step and Node tooling, reversing the earlier no-build-step decision, without a matching benefit at this scope. If `app.js` grows unwieldy, split it into small ES modules (e.g. `recording.js`, `playback.js`, `auth.js`, `preferences.js`) imported from `index.html` — that gets code organization without a build step. Revisit this if a future requirement introduces genuinely complex client state (multi-step flows, many interdependent views), which nothing currently planned does.

### TTS approach: browser-native Web Speech API

For the speak button and hover-to-listen, use the browser's built-in `SpeechSynthesis` API (`window.speechSynthesis`) rather than a server-side TTS model: it's free, needs no new backend dependency, works with the existing no-cloud-calls / open-source ethos, and is a few lines of JS to wire up. Voice quality/availability depends on the user's OS/browser, which is an acceptable tradeoff for this use case. If voice quality becomes a real problem later, a local neural TTS model (e.g. Piper) is the natural upgrade path — same "open, local, CPU-only" spirit as the existing faster-whisper integration — but isn't warranted to start.

### Database: PostgreSQL via a `docker-compose.yml` service, schema managed by Alembic

Moving off SQLite is driven by the app now being multi-user (auth + per-user attempts/preferences): SQLite's single-writer model is a worse fit than Postgres for concurrent authenticated users, and Postgres pairs naturally with running the auth server (Authentik/Keycloak, see Authentication above) as another `docker-compose.yml` service that itself typically wants Postgres. Run Postgres as a `db` service in `docker-compose.yml` (named volume for data, not a bind mount, since Postgres manages its own on-disk format), and switch `app/db.py`'s `create_engine` call from the `sqlite:///` URL to a `postgresql+psycopg://` URL built from env vars (host/port/db/user/password), following `app/config.py`'s existing pattern of computing config at import time from the environment. `psycopg[binary]` is the driver (actively maintained `psycopg3`, prebuilt wheels, no separate libpq install needed in the container).

Schema changes move from `SQLModel.metadata.create_all()` (implicit, additive-only, fine for a throwaway SQLite file) to explicit Alembic migrations, since Postgres is now a persistent shared service that other services (the auth server) and future deployments depend on — ad hoc `create_all()` can't express column drops/renames or data backfills, which real schema evolution eventually needs. `alembic init` generates `app/alembic/`; `env.py` imports `SQLModel.metadata` (all models must already be imported so their tables are registered) as the autogenerate target and reads the DB URL from `app/config.py` rather than duplicating it in `alembic.ini`. Migrations run explicitly (`uv run alembic upgrade head`), not automatically from app startup, so a bad migration doesn't take the app down on boot — run it as a one-off step in local dev and as an explicit step (or init container) in Docker before the app service starts.

### Practice phrase categories: professional registers + phonetics drills

The seeded categories started out as everyday-conversation topics only — `greetings`, `food`, `travel`, `business`, `small-talk`, `tongue-twisters`, `weather`, `technology`. That under-serves the app's actual user: a working non-native speaker whose hardest pronunciation problems are in the vocabulary of their *job*, not at the coffee shop. Latinate legal terms, Greek-rooted clinical vocabulary, and IT jargon with unstable stress (`ˈdeploy` vs. `deˈployment`) are exactly the words people mispronounce in the meetings that matter, and none of them were reachable. So the taxonomy grows along two axes: **professional/domain registers**, and **phonetics-targeted drill sets** that exercise the scorer itself rather than a topic.

`minimal-pairs` is the most valuable of the drill sets and is worth calling out: `ship`/`sheep`, `think`/`sink`, `rice`/`lice` are precisely the contrasts a transcription-only comparison would miss, because Whisper's language model happily "autocorrects" the wrong one into the contextually plausible one. Scoring at the phoneme level is what this app has that a dictation app doesn't, and a category built out of minimal pairs is the direct exercise of it.

**Terminology — `legal`, not `justice`.** The lawyers' professional domain and register is *legal* in English ("legal English", "legal counsel", "legal department", "legal advice"). *Justice* names the abstract ideal or the institution (the court system, a Supreme Court Justice), not the field of practice — a category called `justice` would read as a civics topic rather than a vocabulary set for practising lawyers. Hence the slug `legal`.

**Naming convention**: lowercase, hyphenated, no spaces. The slug is the API contract — it's the `?category=` query value and what a `UserPreference` row stores — while `categoryLabel()` in `frontend/app.js` derives the display text from it (sentence case, hyphens to spaces), so nothing needs a hand-maintained slug → label map.

**Full set (20 categories).** Everyday conversation: `greetings`, `small-talk`, `food`, `travel`, `weather`, `tongue-twisters`. Professional/domain registers: `information-technology`, `medical`, `legal`, `finance`, `business`, `education`, `science`, `engineering`, `customer-service`, `job-interview`, `public-speaking`. Phonetics drills: `minimal-pairs`, `numbers-and-dates`, `idioms`.

**`technology` → `information-technology`**: a rename, not an addition. The seven existing `technology` phrases (wifi passwords, software updates) are already IT-flavoured, and shipping both slugs would put two near-identical options next to each other in the dropdown with no principled way for a user to guess which holds what. The scope broadens with the rename, from consumer gadgets to the workplace IT register. One wrinkle: an existing `UserPreference` row may still store `"technology"`, which then matches no phrase. That degrades safely — `hasOption()` in `frontend/app.js` already ignores a saved category that's no longer offered and falls back to "Any" — but the clean fix is a one-line `UPDATE` carried in the Alembic migration work planned above.

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
- [x] **Frontend test coverage** — `app/tests/test_frontend.py`, 26 headless-Chromium tests via `pytest-playwright` (marker: `frontend`) driving the real shipped `frontend/` files: header/`/api/me` rendering, phrase loading + difficulty filter + failure path, the full record → stop → submit flow, per-word feedback rendering for all four statuses (correct/mispronounced/missing/extra) including phoneme tooltips, history and stats with their empty/error states. Deliberately does **not** start the FastAPI app — a `ThreadingHTTPServer` serves `frontend/` and an `ApiMock` fixture intercepts every `/api/*` call in the browser, so no Whisper/G2p model is ever loaded (~15s vs. ~40s). Chromium runs with `--use-fake-device-for-media-stream`, so the genuine `getUserMedia` + `MediaRecorder` path is exercised rather than stubbed. Server-side frontend wiring (auth gating on `/`, static assets served, `/docs` ungated, plus a contract test asserting every `getElementById` in `app.js` has a matching `id` in `index.html`) lives in `test_auth.py`. One-time setup: `uv run playwright install chromium`.
- [x] Full pytest suite passing (`uv run pytest`) — 79 tests
- [x] Native run verified end-to-end via curl (phrases, random, attempt submission, history, stats)
- [ ] **Manual verification in a real browser**: grant mic permission, record real speech, confirm transcription and scoring behave sensibly on both correct and mispronounced attempts — not yet confirmed by the user. Automated tests use synthetic non-speech audio (silence/sine tone), which validates the pipeline mechanically but can't validate transcription/scoring accuracy on real speech.



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
- [x] `docker-compose.dev.yml` — standalone full-stack dev variant with Authentik auto-configured via an `authentik-blueprints/pronunciation-coach.yaml` blueprint (OAuth2 Provider + Application created declaratively, `AUTHENTIK_BOOTSTRAP_PASSWORD`/`AUTHENTIK_BOOTSTRAP_EMAIL` auto-create `akadmin`) — no manual UI setup. Bootstrap + migrations + blueprint application verified against a real Authentik instance; the blueprint also explicitly sets `grant_types: [authorization_code]` — without it, Authentik rejects every `/application/o/authorize/` request with "Invalid grant_type for provider" (it's not implied by `client_type`, and defaults to empty). Full flow re-verified end-to-end: an authorize request now correctly reaches Authentik's login flow instead of bouncing back with `error=invalid_request`.



### Versioning

- [x] Project versioned as `0.1.0` in `pyproject.toml` / `uv.lock` (bumped from `0.0.1` once authentication and the automated dev stack landed)



### Authentication

- [x] Evaluate open-source, free, easy-to-integrate OAuth2/OIDC auth servers and pick one — chose **Authentik** over Keycloak (see Decisions above: ~250–350MB RAM vs. Keycloak's 400MB–2GB+, no Redis dependency since the 2025.10 release).
- [x] Integrate the OIDC/OAuth2 login flow into the FastAPI backend — `app/auth.py` (Authlib OAuth client, `get_current_user`/`require_web_session` dependencies, `User` model with `Attempt.user_id` FK) and `app/routers/auth.py` (`/auth/login`, `/auth/callback`, `/auth/logout`, `/api/me`); `/api/phrases/*` and `/api/attempts/*` require a session (401 JSON without one), the static frontend redirects to login instead, and attempt history/stats are scoped per-user. `/auth/logout` performs OIDC RP-initiated logout — clearing the local cookie alone left Authentik's own session alive, so `/auth/login` silently re-authorized and Logout appeared to do nothing; it now redirects to the discovered `end_session_endpoint` with `post_logout_redirect_uri` + `id_token_hint`, and the dev blueprint uses `default-invalidation-flow` (the `default-provider-invalidation-flow` default has no stages and ends only the per-app session).
- [x] Add a login/logout flow to the plain-JS frontend — `app.js` calls `/api/me` on load and renders the top-right user menu (hover for identity, click for Logout; see the User menu checklist below).
- [x] Automated test coverage — `app/tests/test_auth.py` (401 without a session, `/api/me` identity, per-user history/stats scoping isolation), `conftest.py` injects a fake authenticated user via `app.dependency_overrides` so `pytest` needs no real Authentik instance.
- [x] Update `README.md` / `CLAUDE.md` (this pass)
- [ ] **Stand up Authentik and complete manual verification** — requires a human + real browser, not done in this pass: bring up `authentik-db`/`authentik-server`/`authentik-worker` via `docker compose up -d`, complete the `akadmin` bootstrap at `/if/flow/initial-setup/`, create the OIDC Provider + Application to get real `AUTHENTIK_CLIENT_ID`/`AUTHENTIK_CLIENT_SECRET`/`AUTHENTIK_ISSUER` values, confirm the `/etc/hosts` `authentik-server` workaround actually resolves the dual-audience issuer problem for this Authentik version, and click through the full login → session → logout flow. Also delete the old `data/pronunciation_coach.db` first — it pre-dates the `user`/`attempt.user_id` columns and there's no migration tooling yet (see Database/Alembic below).



### User menu (frontend)

- [x] Replace the inline "Logged in as X · Logout" header text in `frontend/index.html` / `app.js` with a user icon anchored to the top-right of the logged-in screen — inline SVG glyph in a round `#user-menu-btn`, absolutely positioned inside a now-`position: relative` `<header>`; `header`'s side padding went to a symmetric `3.5rem` so the centred `h1` never collides with it on narrow screens
- [x] On hover, show the logged-in user (email, falling back to `user #<id>`, from the existing `/api/me` call) — a custom `#user-tooltip` span revealed via CSS `opacity` on `.user-menu:hover` / `.user-icon:focus-visible`, chosen over a native `title` so it's assertable in a browser test and styleable with the existing custom properties
- [x] On click, toggle a dropdown menu containing a "Logout" option that navigates to `/auth/logout` — a real `<a href>`, so signing out stays plain navigation with no JS involved. The dropdown repeats the user label above the Logout item, since touch users can't reach the hover tooltip
- [x] Close the menu on outside click, on `Escape`, and on selecting an item; keep it keyboard-reachable — `openUserMenu`/`closeUserMenu`/`toggleUserMenu` keep `aria-expanded` in sync with `hidden`, `Escape` restores focus to the trigger, `ArrowDown` opens and focuses Logout. The button's own click handler calls `stopPropagation()`, otherwise the document-level outside-click listener sees the same click and closes what was just opened
- [x] Style in `style.css` to match the existing look; no new dependencies (vanilla JS, see the Frontend decision above) — all colors come from the existing `:root` custom properties, so dark mode needed no extra rules
- [x] Update the `loadCurrentUser` tests in `app/tests/test_frontend.py` — the three header tests were rewritten against the new markup and six more added (open, close-on-second-click, outside click, `Escape` + focus restore, `ArrowDown`, and Logout navigation). The logout test registers its own `page.route("**/auth/logout", …)`, since `ApiMock` only intercepts `/api/*` and the static test server has no such route. Suite now 55 tests (32 of them `frontend`-marked)

### User preferences

- [x] Add a `UserPreference` (or similar) table keyed by authenticated user ID — `app/models.py`, one row per user (`user_id` FK is `unique`), nullable `difficulty`/`category` since "Any" is a real choice rather than a missing one, plus `updated_at`
- [x] Persist the user's choice (difficulty/category filter) to the database on selection — `savePreferences()` fires on every `change` of either select in `frontend/app.js`, alongside the existing refetch
- [x] Load the user's saved choice as their default when they return, instead of resetting each visit — `init()` in `app.js` fetches categories, then preferences, then the first phrase, so the opening phrase already respects the restored filters instead of visibly swapping out. A saved category that's no longer offered is ignored rather than silently selecting nothing
- [x] Expose an endpoint (e.g. `GET`/`PUT /api/me/preferences`) to read and update it — `app/routers/preferences.py`. `PUT` is a full replacement (an omitted field means "no filter"), `""` is normalized to `NULL` on write, and `GET` returns `{difficulty: null, category: null}` for a user who has never chosen anything so the frontend needs no special case
- [x] Supporting work the feature needed: the frontend had a difficulty select but **no category filter at all**, so a stored category preference would have been unreachable — added a `#category-select` populated by a new `GET /api/phrases/categories` (distinct non-null categories, sorted) and wired into the random-phrase query
- [x] Test coverage — `app/tests/test_preferences.py` (defaults, round-trip, replace-not-merge semantics, `""` normalization, invalid difficulty → 422, per-user scoping, 401 without a session) and 5 browser tests in `test_frontend.py` (category options populated, saved filters restored and applied to the *first* phrase request, selection persisted via `PUT`, stale category ignored, failed preference load falls back to no filters). Suite now 73 tests



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
- [x] **Rename `technology` → `information-technology`** — the 7 existing rows retagged, plus three new workplace-register phrases (deployment, authentication, latency, containerized infrastructure) so the category isn't only consumer gadgets
- [x] **Reconcile existing rows on seed** — the wrinkle the rename exposed: `seed_phrases()` is idempotent *keyed on `text`*, so editing a seeded phrase's category or difficulty never reached an existing `data/pronunciation_coach.db` — it would have shown **both** `technology` and `information-technology` in the dropdown forever. `seed_phrases()` now also updates any existing row whose `(category, difficulty)` drifted from the seed list, making the seed data authoritative for the rows it owns. Stored preferences needed the same treatment: `rename_technology_preferences()` (called from `app/main.py`'s lifespan, alongside seeding) carries a saved `"technology"` filter across the rename. Explicitly a stopgap — it carries a docstring saying to delete it once the equivalent Alembic data migration ships. Without it the frontend degrades safely (`hasOption()` falls back to "Any") but silently discards a choice the user did make
- [x] **Seed ~6 phrases per new category** (2 easy / 2 medium / 2 hard) following the existing `{"text", "difficulty": Difficulty.x, "category"}` dict shape — 133 phrases total, 44 easy / 45 medium / 44 hard. `app/seed_data.py` is now grouped by **category** rather than by difficulty (one `# --- <category> ---` banner each, easy → medium → hard inside): at 20 categories the old difficulty banners scattered each category across three distant blocks and made the coverage rule below impossible to eyeball. Entry order only determines insert order (and therefore `id`) on a fresh DB, and nothing asserts either
- [x] **Give every category at least one phrase at each difficulty**, so no filter combination 404s from `/api/phrases/random`. The three pre-existing gaps are backfilled: `greetings` gained a medium and a hard, `food` a hard, `tongue-twisters` an easy and a medium — `hard`+`greetings`, `hard`+`food` and `easy`+`tongue-twisters` used to return "No phrase matches the given filters"
- [x] **Frontend label prettifying** — `categoryLabel()` in `frontend/app.js` maps hyphens to spaces and applies **sentence** case ("Information technology", "Numbers and dates"), not title case, which would capitalize the joiners ("Numbers And Dates"). Applied to both the select's `option.textContent` and the phrase badge in `renderPhrase()`; `option.value` keeps the raw slug, so the `?category=` query, the stored preference values and `hasOption()` are all untouched
- [x] **Refresh the stale counts** — `README.md` (phrase count + the category list, now grouped by the three themes) and `CLAUDE.md` (count, plus a note on the reconcile behaviour, since "idempotent, keyed off the unique `text` column" was only half the story)
- [x] **Test updates** — `app/tests/test_api.py`'s bound raised to `>= 120`, plus a **coverage-matrix test** asserting all 20 × 3 category/difficulty combinations return 200 (the regression guard that keeps the gap from coming back) and one asserting the rename actually applied. New `app/tests/test_seed_data.py` covers the seed list's internal consistency (unique texts, lowercase-hyphenated slugs, full coverage) and both reconcile paths — a retagged phrase is fixed up without inserting a duplicate, and a stored `"technology"` preference is renamed. In `test_frontend.py`, a new test asserts the prettified label while the option value stays the slug; the Playwright mock's `DEFAULT_CATEGORIES` gained `information-technology` (and `DEFAULT_PHRASE`'s category became the real `tongue-twisters` slug instead of `"tongue twister"`) so the mocks match what the API actually returns. Suite now 79 tests



### Audio playback / TTS (not started)

- [ ] Add a "speak" button next to the target phrase that plays it via the Web Speech API (see Decisions above)
- [ ] Add hover-to-listen on individual words (in the phrase display and/or the per-word feedback results) with a configurable delay (e.g. ~600–1000ms) before triggering, to avoid firing on incidental mouse movement
- [ ] Cancel/debounce in-flight speech synthesis correctly on rapid hover changes or repeated button clicks



### Database: PostgreSQL + Alembic

- [x] Add `psycopg[binary]` (driver) and `alembic` as `pyproject.toml` dependencies — both **runtime**, not dev: the image is built `--no-dev` and the migrate container runs `alembic upgrade head` inside it. `testcontainers[postgres]` went into the dev group
- [x] Add a `db` (Postgres) service to `docker-compose.yml` with a named volume for data and healthcheck; wire the app service's `depends_on` to it — `pronunciation-coach-db`, deliberately separate from `authentik-db` so wiping Authentik's bootstrap doesn't take practice history with it. It gets **no** `user: ${HOST_UID}` override (the postgres image runs `initdb` as root, then drops privileges; forcing a UID breaks first boot — and a named volume means there's no host-ownership problem to solve). Healthcheck interval is 5s, not `authentik-db`'s 30s, because `up` blocks on it twice over
- [x] Add Postgres connection env vars to `app/config.py` (host/port/db/user/password, or a single `DATABASE_URL`), following the existing fail-loudly pattern for required config — both: `DATABASE_URL` overrides wholesale when set, otherwise `POSTGRES_HOST`/`PORT`/`DB`/`USER` (defaulted) + a required-no-default `POSTGRES_PASSWORD`. Built with `URL.create()`, not an f-string, so a password containing `:@/?` is percent-encoded rather than silently corrupting the URL
- [x] Update `app/db.py`'s `create_engine` call to build a `postgresql+psycopg://` URL instead of `sqlite:///` — plus `pool_pre_ping=True` (a Postgres server drops pooled connections; a SQLite file never did) and `-c timezone=utc`. `connect_args={"check_same_thread": False}` had to go; psycopg raises `TypeError` on it
- [x] `alembic init app/alembic`; wire `env.py`'s target metadata to `SQLModel.metadata` and its DB URL to `app/config.py` — `alembic.ini` sits at the repo root (so `uv run alembic` needs no `-c`, and `prepend_sys_path = .` is what lets `env.py` `import app`) and carries **no `sqlalchemy.url`**, keeping the password out of a committed file. `env.py` uses `create_engine()` rather than `engine_from_config()`, since `alembic.ini` is parsed by ConfigParser and a `%` in a password would be read as interpolation syntax
- [x] Generate an initial migration capturing the current schema (`Phrase`, `Attempt`, `User`, `UserPreference`) and verify `alembic upgrade head` produces a schema matching today's `create_all()` output — autogenerated against an empty scratch Postgres, then reviewed against a 9-point checklist; `alembic check` clean, `downgrade base` → `upgrade head` round-trips, `\dT` lists no types. Four schema decisions were settled *before* revision 1, since each would otherwise cost a migration later: `user` → **`app_user`** (reserved word — `SELECT * FROM user` is a syntax error), `Difficulty` as **VARCHAR** via `native_enum=False` (dodges `ALTER TYPE ... ADD VALUE`/`DROP TYPE`, neither of which autogenerate emits), `word_feedback` as **JSONB** (generic `sa.JSON` compiles to PG `json`, which has no `=` operator), and all datetimes as **TIMESTAMPTZ** (the values written are aware, and psycopg3's implicit cast into a naive column runs through the session's TimeZone GUC). A `naming_convention` on `SQLModel.metadata` lives in `app/__init__.py` — the only module guaranteed to run before `models.py`, since SQLAlchemy resolves constraint names at *attach* time
- [x] Remove/replace the current `SQLModel.metadata.create_all()` startup call in `app/main.py`'s lifespan with an explicit migration step (documented in `README.md`/`CLAUDE.md`), not an automatic one — the lifespan now only seeds. Docker gets a one-shot `pronunciation-coach-migrate` init service (`restart: "no"`, quoted — bare `no` is YAML `false`) that the app `depends_on` with `service_completed_successfully`, sharing the app's image tag so the migration is provably the same code. Seeding deliberately **stays** in the lifespan: it's idempotent, it's data the app owns, and it reconciles drifted rows — freezing 133 phrases into a migration would mean a revision per phrase edit
- [x] Update `app/tests/conftest.py`'s test isolation to spin up (or point at) a Postgres instance per test run instead of a SQLite temp file — `testcontainers` by default, `PRONUNCIATION_COACH_TEST_DATABASE_URL` to point at an existing instance. The trick that keeps it cheap: `create_engine()` doesn't connect, so only the *URL* must exist at import time (where `app/db.py` builds the engine) and the container can start lazily in a session-scoped `database` fixture — the `frontend`-marked tests never request it, so they still run in ~23s with no Docker at all. A `DROP SCHEMA public CASCADE` at session start restores the fresh-database guarantee the tmpdir gave (several tests assert exact row counts and insert hard-coded unique `sub`s), and refuses any database whose name lacks `test`
- [x] Update `CLAUDE.md` (architecture notes, commands) and `README.md` (setup/config) once implemented — plus a new `app/tests/test_migrations.py` running `alembic check`, so model-vs-migration drift fails the suite rather than surfacing as a missing column at runtime. `rename_technology_preferences()` was deleted with **no** replacement data migration: revision 1 *creates* the tables, so no Postgres database can ever hold the stale `"technology"` value, and a migration that provably cannot update a row implies a history that didn't happen



## Open items

- [ ] Manual real-microphone pronunciation test in a browser (see Testing & verification above) — the one requirement that still needs a human to confirm.
- [ ] Stand up Authentik and complete manual login/logout verification in a browser (see Authentication checklist above) — code is implemented and tested, but needs a human to bootstrap the real auth server and click through the flow.
- [x] Persist user choices in the database (see User preferences checklist above) — done: `UserPreference` table, `GET`/`PUT /api/me/preferences`, and difficulty + category selects restored on load.
- [x] Expand the practice-phrase categories from 8 to 20 — professional registers (medical, legal, information-technology, …) plus phonetics drill sets (see Practice phrase categories checklist above) — done: 133 phrases, every category covering all three difficulties.
- [ ] Speak button + hover-to-listen TTS (see Audio playback / TTS checklist above) — not yet started.
- [x] Migrate from SQLite to PostgreSQL with Alembic-managed schema (see Database checklist above) — done: `pronunciation-coach-db` service, `postgresql+psycopg://`, one initial migration, `create_all()` gone from the lifespan, and a testcontainers-backed test suite.

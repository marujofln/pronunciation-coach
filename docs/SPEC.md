# Pronunciation Coach — Spec & Tasks

This file is the source of truth for requirements and build status. For "how do I run it" see `README.md`; for "how is it built" see `CLAUDE.md`.

## Overview

A local, single-user web app for practicing English pronunciation: pick a phrase, record yourself saying it in the browser, and get phoneme-level feedback on pronunciation accuracy from an open Whisper model plus a grapheme-to-phoneme scoring pipeline.

## Requirements

- Record phrase audio in the browser (`MediaRecorder`) and transcribe it locally with an open Whisper model — no cloud API calls.
- Score pronunciation at the **phoneme level**, not just word-level transcription match: convert both the target phrase and the transcript to phonemes and compare, so mispronunciations Whisper's language model might "autocorrect" past still get caught. Return per-word feedback (correct / mispronounced / missing / extra) with expected vs. heard phonemes.
- Practice phrases come from a seeded database, filterable/selectable by difficulty and category.
- Every attempt (transcript, score, per-word feedback) is persisted, with history and basic stats (average score, per-phrase averages) viewable.
- Frontend is plain HTML/CSS/JS with no build step, served directly by the backend.
- Backend is FastAPI, following the `fastapi` skill's conventions (Annotated dependencies, no Ellipsis defaults, no RootModel, return-type-driven serialization, router-level prefix/tags, SQLModel, uv for dependency management).
- User authentication: authenticate users against an external authentication server (OAuth2/OIDC) — preferably open-source, easy to integrate with this FastAPI + plain-JS stack, and free of charge. Supersedes the original v0.0.1 "no auth, single local user" scope (see Authentication checklist below).
- Persist each authenticated user's choices (e.g. their difficulty/category filter selection) in the database, tied to their account, so preferences carry over between visits.
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

## Build checklist



### Core app

- [x] Scaffold uv project (`pyproject.toml`, `[tool.fastapi]` entrypoint, runtime + dev dependencies)
- [x] `app/config.py` (env-driven paths, self-contained `data/` dir) and `app/db.py` (SQLModel engine/session)
- [x] `app/models.py` — `Phrase` and `Attempt` SQLModel tables
- [x] `app/schemas.py` — API request/response models (`WordFeedback`, `PhraseRead`, `AttemptRead`, `AttemptResult`, `StatsRead`)
- [x] `app/seed_data.py` — ~50 seeded phrases across difficulty/category, idempotent seeding
- [x] `app/ml.py` — Whisper (`small.en`, CPU, int8) and G2p model loading, once at startup, nltk `<3.9` compatibility fix
- [x] `app/scoring.py` — normalization, per-word G2P, `difflib` word alignment, phoneme edit-distance scoring
- [x] `app/routers/phrases.py` and `app/routers/attempts.py` — all endpoints
- [x] `app/main.py` — lifespan wiring, router registration, `app.frontend()` static mount
- [x] `frontend/` — `index.html`, `app.js` (record/submit/render), `style.css`



### Testing & verification

- [x] `app/tests/` — unit tests for the scoring algorithm (hand-crafted ARPAbet cases) and `TestClient` smoke tests (phrases, attempts, history, stats) with an isolated data dir and synthetic WAV audio
- [x] Full pytest suite passing (`uv run pytest`)
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
- [x] Integrate the OIDC/OAuth2 login flow into the FastAPI backend — `app/auth.py` (Authlib OAuth client, `get_current_user`/`require_web_session` dependencies, `User` model with `Attempt.user_id` FK) and `app/routers/auth.py` (`/auth/login`, `/auth/callback`, `/auth/logout`, `/api/me`); `/api/phrases/*` and `/api/attempts/*` require a session (401 JSON without one), the static frontend redirects to login instead, and attempt history/stats are scoped per-user.
- [x] Add a login/logout flow to the plain-JS frontend — header shows "Logged in as X · Logout" via a new `/api/me` call in `app.js`.
- [x] Automated test coverage — `app/tests/test_auth.py` (401 without a session, `/api/me` identity, per-user history/stats scoping isolation), `conftest.py` injects a fake authenticated user via `app.dependency_overrides` so `pytest` needs no real Authentik instance.
- [x] Update `README.md` / `CLAUDE.md` (this pass)
- [ ] **Stand up Authentik and complete manual verification** — requires a human + real browser, not done in this pass: bring up `authentik-db`/`authentik-server`/`authentik-worker` via `docker compose up -d`, complete the `akadmin` bootstrap at `/if/flow/initial-setup/`, create the OIDC Provider + Application to get real `AUTHENTIK_CLIENT_ID`/`AUTHENTIK_CLIENT_SECRET`/`AUTHENTIK_ISSUER` values, confirm the `/etc/hosts` `authentik-server` workaround actually resolves the dual-audience issuer problem for this Authentik version, and click through the full login → session → logout flow. Also delete the old `data/pronunciation_coach.db` first — it pre-dates the `user`/`attempt.user_id` columns and there's no migration tooling yet (see Database/Alembic below).



### User preferences (not started, depends on Authentication)

- [ ] Add a `UserPreference` (or similar) table keyed by authenticated user ID
- [ ] Persist the user's choice (difficulty/category filter) to the database on selection
- [ ] Load the user's saved choice as their default when they return, instead of resetting each visit
- [ ] Expose an endpoint (e.g. `GET`/`PUT /api/me/preferences`) to read and update it



### Audio playback / TTS (not started)

- [ ] Add a "speak" button next to the target phrase that plays it via the Web Speech API (see Decisions above)
- [ ] Add hover-to-listen on individual words (in the phrase display and/or the per-word feedback results) with a configurable delay (e.g. ~600–1000ms) before triggering, to avoid firing on incidental mouse movement
- [ ] Cancel/debounce in-flight speech synthesis correctly on rapid hover changes or repeated button clicks



### Database: PostgreSQL + Alembic (not started)

- [ ] Add `psycopg[binary]` (driver) and `alembic` as `pyproject.toml` dependencies
- [ ] Add a `db` (Postgres) service to `docker-compose.yml` with a named volume for data and healthcheck; wire the app service's `depends_on` to it
- [ ] Add Postgres connection env vars to `app/config.py` (host/port/db/user/password, or a single `DATABASE_URL`), following the existing fail-loudly pattern for required config
- [ ] Update `app/db.py`'s `create_engine` call to build a `postgresql+psycopg://` URL instead of `sqlite:///`
- [ ] `alembic init app/alembic`; wire `env.py`'s target metadata to `SQLModel.metadata` and its DB URL to `app/config.py`
- [ ] Generate an initial migration capturing the current schema (`Phrase`, `Attempt`, `User`) and verify `alembic upgrade head` produces a schema matching today's `create_all()` output
- [ ] Remove/replace the current `SQLModel.metadata.create_all()` startup call in `app/main.py`'s lifespan with an explicit migration step (documented in `README.md`/`CLAUDE.md`), not an automatic one
- [ ] Update `app/tests/conftest.py`'s test isolation to spin up (or point at) a Postgres instance per test run instead of a SQLite temp file — likely a `testcontainers` Postgres or a dedicated `docker-compose` test service
- [ ] Update `CLAUDE.md` (architecture notes, commands) and `README.md` (setup/config) once implemented



## Open items

- [ ] Manual real-microphone pronunciation test in a browser (see Testing & verification above) — the one requirement that still needs a human to confirm.
- [ ] Stand up Authentik and complete manual login/logout verification in a browser (see Authentication checklist above) — code is implemented and tested, but needs a human to bootstrap the real auth server and click through the flow.
- [ ] Persist user choices in the database (see User preferences checklist above) — not yet started, depends on authentication being in place first.
- [ ] Speak button + hover-to-listen TTS (see Audio playback / TTS checklist above) — not yet started.
- [ ] Migrate from SQLite to PostgreSQL with Alembic-managed schema (see Database checklist above) — not yet started.
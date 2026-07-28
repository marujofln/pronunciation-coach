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

## Decisions

### Frontend: stay with vanilla JS, no framework

The feature set is escalating (auth login/logout, persisted preferences, TTS playback with a speak button and per-word hover timers, on top of the existing recording/scoring/history/stats UI), which raises the question of whether a frontend framework (React/Vue/Svelte) is now the better choice over plain HTML/CSS/JS.

**Recommendation: stay with vanilla JS.** None of the planned features need component reactivity or complex state trees — TTS playback is a couple of `SpeechSynthesis` calls, hover-to-listen is a `mouseenter`/`mouseleave` timer, an auth flow is a redirect plus a token check, and preferences are one more field on existing fetch/render calls. All of that fits the state-object-plus-render-functions pattern `app.js` already uses. Adopting a framework would mean a build step and Node tooling, reversing the earlier no-build-step decision, without a matching benefit at this scope. If `app.js` grows unwieldy, split it into small ES modules (e.g. `recording.js`, `playback.js`, `auth.js`, `preferences.js`) imported from `index.html` — that gets code organization without a build step. Revisit this if a future requirement introduces genuinely complex client state (multi-step flows, many interdependent views), which nothing currently planned does.

### TTS approach: browser-native Web Speech API

For the speak button and hover-to-listen, use the browser's built-in `SpeechSynthesis` API (`window.speechSynthesis`) rather than a server-side TTS model: it's free, needs no new backend dependency, works with the existing no-cloud-calls / open-source ethos, and is a few lines of JS to wire up. Voice quality/availability depends on the user's OS/browser, which is an acceptable tradeoff for this use case. If voice quality becomes a real problem later, a local neural TTS model (e.g. Piper) is the natural upgrade path — same "open, local, CPU-only" spirit as the existing faster-whisper integration — but isn't warranted to start.

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

### Versioning
- [x] Project versioned as `0.0.1` in `pyproject.toml` / `uv.lock`

### Authentication (not started)
- [ ] Evaluate open-source, free, easy-to-integrate OAuth2/OIDC auth servers and pick one. Candidates to start from: **Keycloak** (most established, Apache-2.0, official Docker image, extensive docs) and **Authentik** (lighter-weight, friendlier setup, also free/open-source) — either integrates via standard OIDC, so the pick mainly comes down to ops simplicity.
- [ ] Stand up the chosen auth server, likely as an additional `docker-compose.yml` service alongside the app
- [ ] Integrate the OIDC/OAuth2 login flow into the FastAPI backend (token verification dependency, protect `/api/*` routes)
- [ ] Add a login/logout flow to the plain-JS frontend
- [ ] Update `README.md` / `CLAUDE.md` once implemented (setup steps, new env vars, architecture notes)

### User preferences (not started, depends on Authentication)
- [ ] Add a `UserPreference` (or similar) table keyed by authenticated user ID
- [ ] Persist the user's choice (difficulty/category filter) to the database on selection
- [ ] Load the user's saved choice as their default when they return, instead of resetting each visit
- [ ] Expose an endpoint (e.g. `GET`/`PUT /api/me/preferences`) to read and update it

### Audio playback / TTS (not started)
- [ ] Add a "speak" button next to the target phrase that plays it via the Web Speech API (see Decisions above)
- [ ] Add hover-to-listen on individual words (in the phrase display and/or the per-word feedback results) with a configurable delay (e.g. ~600–1000ms) before triggering, to avoid firing on incidental mouse movement
- [ ] Cancel/debounce in-flight speech synthesis correctly on rapid hover changes or repeated button clicks

## Open items

- [ ] Manual real-microphone pronunciation test in a browser (see Testing & verification above) — the one requirement that still needs a human to confirm.
- [ ] Authentication server integration (see Authentication checklist above) — not yet started.
- [ ] Persist user choices in the database (see User preferences checklist above) — not yet started, depends on authentication being in place first.
- [ ] Speak button + hover-to-listen TTS (see Audio playback / TTS checklist above) — not yet started.

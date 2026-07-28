# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Docker is the preferred way to *run* the app (see `Dockerfile` / `docker-compose.yml`); `uv` is for local development (tests, lint, editing with reload).

```bash
HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose up -d --build   # build + run (preferred)
docker compose logs -f                                             # tail logs
docker compose down                                                 # stop and remove

uv sync                    # install/update dependencies
uv run fastapi dev         # dev server with reload (entrypoint from [tool.fastapi] in pyproject.toml)
uv run fastapi run         # production server, native
uv run pytest              # run all tests
uv run pytest app/tests/test_scoring.py::test_identical_text_scores_100   # single test
uv run ruff check .        # lint
uv run ruff format .       # format
```

No separate build step — the frontend is plain static files served directly by FastAPI.

## Architecture

This is a local, single-user FastAPI app: record yourself saying an English phrase, get a phoneme-level pronunciation score.

**Scoring pipeline** (the core of the app, spans `app/ml.py`, `app/scoring.py`, `app/routers/attempts.py`): uploaded audio → `faster-whisper` transcribes it to text → `app/scoring.py` normalizes both the target phrase and the transcript into word lists → `g2p_en` converts each word *individually* to ARPAbet phonemes (called per-word, not per-sentence, to avoid the `" "` separator tokens `g2p_en` inserts between words on sentence input) → `difflib.SequenceMatcher` aligns reference/hypothesis word lists (equal/replace/delete/insert opcodes map to correct/mispronounced/missing/extra) → phoneme-level edit distance per aligned word pair produces a 0–1 word score → the overall 0–100 score is the mean word score across all non-`extra` words.

**Model lifecycle**: `WhisperModel` and `G2p` are both expensive to load and are instantiated exactly once, in `app/main.py`'s lifespan, and stashed on `app.state`. Request handlers reach them via the `WhisperModelDep`/`G2pDep` dependency aliases in `app/ml.py` — never re-instantiated per request. The Whisper model defaults to `small.en` / `compute_type="int8"` / `device="cpu"`, overridable via the `WHISPER_MODEL_SIZE` / `WHISPER_COMPUTE_TYPE` env vars.

**Self-contained runtime data**: `app/config.py` computes every runtime path (SQLite DB, saved recordings, Whisper model cache, nltk data) under `data/`, and sets the `NLTK_DATA` env var *before nltk is ever imported anywhere in the process* — order matters here, since nltk's `default_download_dir()` only picks a directory that already exists on disk at first use, and always falls back to `~/nltk_data` otherwise. The whole `data/` root is overridable via `PRONUNCIATION_COACH_DATA_DIR` (this is how tests get an isolated runtime).

**nltk is pinned `<3.9`**: `g2p_en`'s own downloader requests the legacy `averaged_perceptron_tagger` resource, but nltk ≥3.9 looks up `averaged_perceptron_tagger_eng` by default — a mismatch that surfaces as a `LookupError` on first real use, not at import time. `ensure_nltk_data()` in `app/ml.py` defensively tries both resource names as a second line of defense.

**Frontend**: plain HTML/CSS/JS in `frontend/`, no bundler. Served via FastAPI's `app.frontend("/", directory=...)`, a low-priority static route mounted *after* the API routers in `app/main.py` so it never shadows `/api/*`.

**Data model** (`app/models.py`): `Phrase` (unique `text`, `difficulty`, `category`) and `Attempt` (FK to phrase, `transcript`, `score`, `word_feedback` stored as a JSON column). `app/seed_data.py` seeds ~50 built-in phrases idempotently on every startup, keyed off the unique `text` column.

**Docker**: `docker-compose.yml` bind-mounts `./data:/app/data`, so the SQLite DB and downloaded Whisper/nltk caches are shared between Docker and native runs and survive container rebuilds. The container runs as `${HOST_UID}:${HOST_GID}` (defaulting to 1000:1000) rather than root, specifically so files written into that bind mount are owned by the host user instead of `root` — set `HOST_UID`/`HOST_GID` (e.g. via a gitignored `.env`) to your actual `id -u`/`id -g` if they differ from 1000.

**Test isolation** (`app/tests/conftest.py`): sets `PRONUNCIATION_COACH_DATA_DIR` to a fresh temp dir as top-level module code — this must run before `app.config` (and therefore `app.main`) is imported anywhere, including by other test files, which is why it happens before any other import in the file. The session-scoped `client` fixture then runs the app's real lifespan via `with TestClient(app)`, so tests exercise real model loading and startup seeding, not mocks.

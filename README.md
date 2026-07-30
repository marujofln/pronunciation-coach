[Português (Brasil)](README_pt_BR.md)

# Pronunciation Coach

A local web app for practicing English pronunciation. Pick a phrase, record yourself saying it, and get instant feedback: an open Whisper model transcribes your recording, and a phoneme-level scoring pipeline compares it against the target phrase to highlight exactly which words (and sounds) you got right or wrong.

## Features

- **Practice phrases** — seeded database of 133 English phrases across difficulty levels (easy/medium/hard) and 20 categories, every one of them offering all three difficulties:
  - *everyday conversation* — greetings, small-talk, food, travel, weather, tongue-twisters
  - *professional registers* — information-technology, medical, legal, finance, business, education, science, engineering, customer-service, job-interview, public-speaking
  - *phonetics drills* — minimal-pairs (ship/sheep, think/sink), numbers-and-dates (thirteen/thirty), idioms
- **Speech-to-text** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`small.en`, CPU, int8) transcribes your recording locally, no cloud API calls.
- **Phoneme-level scoring** — both the target phrase and your transcript are converted to ARPAbet phonemes ([g2p_en](https://github.com/Kyubyong/g2p)) and compared with phoneme edit-distance, so the score reflects actual pronunciation accuracy rather than just "did Whisper understand the words." Per-word feedback shows expected vs. heard phonemes.
- **Hear it done right** — a speak button plays the target phrase, and after scoring you can hover (or tap) any word in the feedback to hear that word on its own, so a mispronounced word comes with a reference rather than just a red mark. Uses the browser's built-in Web Speech API — no extra service, no cloud call, no new dependency.
- **Attempt history** — every recording, transcript, and score is saved to PostgreSQL, with a running average and per-phrase stats. Schema changes ship as [Alembic](https://alembic.sqlalchemy.org/) migrations.
- **Saved preferences** — your difficulty and category filter selection is remembered in your browser and restored on your next visit, so you don't re-pick it every time.
- **No accounts, no login** — it's a local single-user app; there's nothing to sign up for and no identity provider to stand up.
- **No build step** — the frontend is plain HTML/CSS/JS served directly by FastAPI.

No GPU required — the default model is tuned for CPU inference.

## Getting started (Docker, preferred)

The preferred way to run the app is via Docker — it needs nothing installed locally besides Docker itself.

**Requirements:** Docker and Docker Compose. The only configuration is a database password, which has no default — the stack refuses to start rather than fall back to something guessable.

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')" >> .env
echo "HOST_UID=$(id -u)" >> .env
echo "HOST_GID=$(id -g)" >> .env
docker compose up -d --build
```

`.env` is gitignored and machine-specific. `HOST_UID`/`HOST_GID` make the container run as your host user rather than root, so files written into the bind-mounted `data/` dir (saved recordings, model caches) are owned by you, not `root`.

`docker compose up` starts three services: `pronunciation-coach-db` (PostgreSQL), a one-shot `pronunciation-coach-migrate` that runs `alembic upgrade head` and exits, then `pronunciation-coach` itself once the migration has completed successfully. Migrations are deliberately *not* applied from the app's startup, so a bad migration fails visibly in the migrate container instead of crash-looping the app.

The database lives in a named Docker volume (`pronunciation-coach-db-data`), not in `data/` — so unlike the old SQLite file, **`docker compose down -v` destroys your practice history**. Plain `docker compose down` does not.

Open <http://localhost:8000>, allow microphone access, and start recording.

On first run, the app downloads the Whisper model (~150MB) and nltk's `cmudict`/POS-tagger data into `data/` (bind-mounted from the host) — this needs internet access once, after which everything runs offline, even across container rebuilds.

Useful commands: `docker compose logs -f` (tail logs), `docker compose down` (stop and remove the container), `docker compose up -d --build` (rebuild after changing dependencies or code).

## Getting started (native, for development)

Running natively with `uv` is faster to iterate on when editing code, since `fastapi dev` gives you auto-reload.

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/), `ffmpeg` (used by faster-whisper's audio decoding), and a reachable PostgreSQL. The easiest one to borrow is the dev stack's, which publishes on host port 55432:

```bash
docker compose -f docker-compose.dev.yml up -d pronunciation-coach-db
export DATABASE_URL=postgresql+psycopg://pronunciation_coach:dev-insecure-app-postgres-password@127.0.0.1:55432/pronunciation_coach
```

```bash
uv sync
uv run alembic upgrade head   # apply migrations first — the app no longer creates its own schema
uv run fastapi dev
```

Same first-run model/nltk download behavior as above, into the same `data/` dir either way. For a production-style native run (no auto-reload): `uv run fastapi run`.

## Upgrading an existing local install

Earlier versions of this app kept its data in a SQLite file and, briefly, gated everything behind an [Authentik](https://goauthentik.io/) OIDC login with per-account history. Both are gone, and there is no upgrade path from either — recreate the database:

```bash
docker compose down -v          # destroys the old volume; see the warning above
rm -f data/pronunciation_coach.db
docker compose up -d --build
```

The migrate service creates the schema and the app reseeds the phrases on startup. Saved recordings under `data/audio/` are untouched, but the attempt rows that referenced them are not carried over. From here on, schema changes ship as Alembic migrations (`uv run alembic upgrade head`) rather than as "delete your database".

The Authentik integration is not deleted, just not shipped: it lives on the `auth-authentik` branch if you need to authenticate a shared deployment.

## Development stack

For local development/testing, `docker-compose.dev.yml` brings up the same stack with dev-only secrets baked in — no `.env` setup at all.

```bash
git switch dev
docker compose -f docker-compose.dev.yml up -d --build
```

The app service builds the working tree rather than a pinned ref, so the stack runs whatever is checked out — uncommitted edits included. Day-to-day work lands on the `dev` branch, which is why the snippet switches to it first; `master` only receives explicitly requested pushes.

It also publishes Postgres on host port **55432**, which is what the native-development section above borrows.

**This file's secrets are hardcoded, non-random, dev-only placeholders on purpose** — safe to commit, safe to share, and clearly named so they can't be mistaken for something real (`dev-insecure-...`). Never reuse any value from it for a real or shared deployment; use the regular `docker-compose.yml` for that. It's a full standalone duplicate of `docker-compose.yml` (not an override layer) with its own volume names, so both stacks can coexist on the same machine without colliding — bring one down (`docker compose [-f docker-compose.dev.yml] down`) before starting the other if you're switching between them, since they both publish host port 8000.

## Configuration

All configuration is via environment variables (see `app/config.py`), settable either natively or in `docker-compose.yml`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WHISPER_MODEL_SIZE` | `small.en` | faster-whisper model size (e.g. `base.en`, `medium.en`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | CTranslate2 compute type |
| `PRONUNCIATION_COACH_DATA_DIR` | `./data` | Root directory for saved recordings and the model/nltk caches (not the database — that's Postgres) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` | This app's database server |
| `POSTGRES_DB` / `POSTGRES_USER` | `pronunciation_coach` / `pronunciation_coach` | This app's database name and role |
| `POSTGRES_PASSWORD` | *(required, no default)* | Password for the app's database |
| `DATABASE_URL` | *(unset)* | Full SQLAlchemy URL (e.g. `postgresql+psycopg://user:pw@host/db`). When set it overrides all five `POSTGRES_*` vars — the escape hatch for a managed database, a unix socket, or connection query params |
| `HOST_UID` / `HOST_GID` | `1000` / `1000` | Docker only — UID/GID the container runs as, so bind-mounted files match your host user |

## Development

```bash
uv run pytest          # run the test suite
uv run ruff check .    # lint
uv run ruff format .   # format
```

The test suite needs no database setup: it starts a throwaway `postgres:16-alpine` via [testcontainers](https://testcontainers-python.readthedocs.io/) on first use, resets the schema, and applies the migrations. Only tests that actually touch the database trigger it — the browser-driven `frontend`-marked tests never start Docker. To run against an already-running Postgres instead (CI, or faster repeat runs), set `PRONUNCIATION_COACH_TEST_DATABASE_URL`; the suite drops and recreates the `public` schema at session start, and refuses to touch a database whose name doesn't contain `test`.

### Migrations

```bash
uv run alembic upgrade head                        # apply pending migrations
uv run alembic revision --autogenerate -m "..."    # after editing app/models.py
uv run alembic check                               # models vs. migrations drift check
uv run alembic downgrade -1                        # roll back one revision
```

Autogenerate diffs `app/models.py` against the *live* database, so point it at one that's already at head. Always read the generated revision before committing it — autogenerate is a first draft, not an oracle. `alembic check` also runs as a test (`app/tests/test_migrations.py`), so a model change without a migration fails the suite rather than surfacing as a missing column at runtime.

See `CLAUDE.md` for architecture notes.

## Project layout

```text
app/
├── main.py         # FastAPI app, startup lifespan, router/frontend wiring
├── __init__.py      # SQLModel constraint naming convention (must load before models)
├── config.py         # env-driven paths and database URL
├── db.py              # SQLModel engine/session
├── alembic/            # migration environment + versions/
├── models.py            # Phrase, Attempt table models
├── schemas.py            # API request/response models
├── seed_data.py           # built-in practice phrases
├── ml.py                   # Whisper + G2p model loading
├── scoring.py               # phoneme alignment & scoring algorithm
├── routers/                  # /api/phrases, /api/attempts
└── tests/                     # pytest suite
frontend/
├── index.html
├── app.js            # recording, submission, results rendering, TTS playback
└── style.css
alembic.ini
Dockerfile
docker-compose.yml
docker-compose.dev.yml   # standalone dev stack with dev-only secrets
```

## License

This project is licensed under the BSD 3-Clause License. See [LICENSE](LICENSE) for details.

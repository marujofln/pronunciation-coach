# Pronunciation Coach

A local web app for practicing English pronunciation. Pick a phrase, record yourself saying it, and get instant feedback: an open Whisper model transcribes your recording, and a phoneme-level scoring pipeline compares it against the target phrase to highlight exactly which words (and sounds) you got right or wrong.

## Features

- **Practice phrases** — seeded database of ~50 English phrases across difficulty levels (easy/medium/hard) and categories (greetings, food, travel, business, small-talk, tongue-twisters, weather, technology).
- **Speech-to-text** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`small.en`, CPU, int8) transcribes your recording locally, no cloud API calls.
- **Phoneme-level scoring** — both the target phrase and your transcript are converted to ARPAbet phonemes ([g2p_en](https://github.com/Kyubyong/g2p_en)) and compared with phoneme edit-distance, so the score reflects actual pronunciation accuracy rather than just "did Whisper understand the words." Per-word feedback shows expected vs. heard phonemes.
- **Attempt history** — every recording, transcript, and score is saved, with a running average and per-phrase stats.
- **No build step** — the frontend is plain HTML/CSS/JS served directly by FastAPI.

No GPU required — the default model is tuned for CPU inference.

## Getting started (Docker, preferred)

The preferred way to run the app is via Docker — it needs nothing installed locally besides Docker itself.

**Requirements:** Docker and Docker Compose.

```bash
HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose up -d --build
```

Or, to avoid typing that every time, put it in a `.env` file in the project root (gitignored, machine-specific) and just run `docker compose up -d`:

```bash
echo "HOST_UID=$(id -u)" >> .env
echo "HOST_GID=$(id -g)" >> .env
docker compose up -d
```

`HOST_UID`/`HOST_GID` make the container run as your host user rather than root, so files written into the bind-mounted `data/` dir (the SQLite DB, saved recordings) are owned by you, not `root`.

Open http://localhost:8000, allow microphone access, and start recording.

On first run, the app downloads the Whisper model (~150MB) and nltk's `cmudict`/POS-tagger data into `data/` (bind-mounted from the host) — this needs internet access once, after which everything runs offline, even across container rebuilds.

Useful commands: `docker compose logs -f` (tail logs), `docker compose down` (stop and remove the container), `docker compose up -d --build` (rebuild after changing dependencies or code).

## Getting started (native, for development)

Running natively with `uv` is faster to iterate on when editing code, since `fastapi dev` gives you auto-reload.

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/), `ffmpeg` (used by faster-whisper's audio decoding).

```bash
uv sync
uv run fastapi dev
```

Same first-run download behavior as above, into the same `data/` dir either way. For a production-style native run (no auto-reload): `uv run fastapi run`.

## Configuration

All configuration is via environment variables (see `app/config.py`), settable either natively or in `docker-compose.yml`:

| Variable | Default | Purpose |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `small.en` | faster-whisper model size (e.g. `base.en`, `medium.en`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | CTranslate2 compute type |
| `PRONUNCIATION_COACH_DATA_DIR` | `./data` | Root directory for the SQLite DB, saved recordings, and model/nltk caches |
| `HOST_UID` / `HOST_GID` | `1000` / `1000` | Docker only — UID/GID the container runs as, so bind-mounted files match your host user |

## Development

```bash
uv run pytest          # run the test suite
uv run ruff check .    # lint
uv run ruff format .   # format
```

See `CLAUDE.md` for architecture notes.

## Project layout

```
app/
├── main.py         # FastAPI app, startup lifespan, router/frontend wiring
├── config.py        # env-driven paths
├── db.py             # SQLModel engine/session
├── models.py          # Phrase, Attempt table models
├── schemas.py          # API request/response models
├── seed_data.py         # built-in practice phrases
├── ml.py                 # Whisper + G2p model loading
├── scoring.py             # phoneme alignment & scoring algorithm
├── routers/                # /api/phrases, /api/attempts
└── tests/                    # pytest suite
frontend/
├── index.html
├── app.js            # recording, submission, results rendering
└── style.css
Dockerfile
docker-compose.yml
```

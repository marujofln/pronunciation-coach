# Pronunciation Coach

A local web app for practicing English pronunciation. Pick a phrase, record yourself saying it, and get instant feedback: an open Whisper model transcribes your recording, and a phoneme-level scoring pipeline compares it against the target phrase to highlight exactly which words (and sounds) you got right or wrong.

## Features

- **Practice phrases** — seeded database of 133 English phrases across difficulty levels (easy/medium/hard) and 20 categories, every one of them offering all three difficulties:
  - *everyday conversation* — greetings, small-talk, food, travel, weather, tongue-twisters
  - *professional registers* — information-technology, medical, legal, finance, business, education, science, engineering, customer-service, job-interview, public-speaking
  - *phonetics drills* — minimal-pairs (ship/sheep, think/sink), numbers-and-dates (thirteen/thirty), idioms
- **Speech-to-text** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`small.en`, CPU, int8) transcribes your recording locally, no cloud API calls.
- **Phoneme-level scoring** — both the target phrase and your transcript are converted to ARPAbet phonemes ([g2p_en](https://github.com/Kyubyong/g2p_en)) and compared with phoneme edit-distance, so the score reflects actual pronunciation accuracy rather than just "did Whisper understand the words." Per-word feedback shows expected vs. heard phonemes.
- **Attempt history** — every recording, transcript, and score is saved per account, with a running average and per-phrase stats.
- **Saved preferences** — your difficulty and category filter selection is stored against your account and restored on your next visit, so you don't re-pick it every time.
- **Authentication** — the whole app sits behind [Authentik](https://goauthentik.io/) (open-source OIDC), so history/stats are scoped to your own account.
- **No build step** — the frontend is plain HTML/CSS/JS served directly by FastAPI.

No GPU required — the default model is tuned for CPU inference.

## Getting started (Docker, preferred)

The preferred way to run the app is via Docker — it needs nothing installed locally besides Docker itself.

**Requirements:** Docker and Docker Compose. The app also requires a one-time [Authentication setup](#authentication-setup) before it will start — it fails loudly if the auth env vars aren't set, rather than running insecurely.

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

## Authentication setup

The whole app requires login via [Authentik](https://goauthentik.io/), a self-hosted OIDC identity provider that runs alongside the app as three more `docker-compose.yml` services (`authentik-db`, `authentik-server`, `authentik-worker`). One-time setup, before the app itself will start:

1. Make `authentik-server` resolvable from your browser, not just from inside Docker — the app (in-container) and your browser (on the host) both need to reach Authentik at the *same* hostname for OIDC discovery to produce a browser-usable login URL:

   ```bash
   echo "127.0.0.1 authentik-server" | sudo tee -a /etc/hosts
   ```

2. Generate secrets into your `.env` (gitignored):

   ```bash
   echo "AUTHENTIK_SECRET_KEY=$(openssl rand -base64 60 | tr -d '\n')" >> .env
   echo "AUTHENTIK_PG_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')" >> .env
   echo "SESSION_SECRET_KEY=$(openssl rand -base64 32 | tr -d '\n')" >> .env
   ```

3. Bring up just Authentik first: `docker compose up -d authentik-db authentik-server authentik-worker`.
4. Visit `http://authentik-server:9000/if/flow/initial-setup/` and set a password for the default `akadmin` user.
5. In the Authentik admin UI, create an **OAuth2/OIDC Provider** and an **Application** using it (suggested slug: `pronunciation-coach`, redirect URI: `http://localhost:8000/auth/callback`).
6. Copy the provider's client ID/secret and the application's issuer URL into `.env`:

   ```bash
   echo "AUTHENTIK_ISSUER=http://authentik-server:9000/application/o/pronunciation-coach/" >> .env
   echo "AUTHENTIK_CLIENT_ID=<from the Authentik UI>" >> .env
   echo "AUTHENTIK_CLIENT_SECRET=<from the Authentik UI>" >> .env
   ```

7. Start the app itself: `docker compose up -d --build pronunciation-coach`.

Visiting the app now redirects to Authentik's login page if you don't already have a session.

**Upgrading an existing local install**: this release added a `user` table and a required `Attempt.user_id` column. There's no migration tooling yet (see `docs/SPEC.md`'s Database/Alembic entry) — delete `data/pronunciation_coach.db` before your first run on the new schema; it's recreated (and reseeded) automatically.

## Development stack (fully automated)

For local development/testing, `docker-compose.dev.yml` brings up the *entire* stack — the app and Authentik — with Authentik's OIDC Provider + Application created automatically via an [Authentik blueprint](https://docs.goauthentik.io/customize/blueprints/) (`authentik-blueprints/pronunciation-coach.yaml`). No manual UI clicking, no `.env` setup.

```bash
echo "127.0.0.1 authentik-server" | sudo tee -a /etc/hosts   # one-time, same reason as above
git switch dev
docker compose -f docker-compose.dev.yml up -d --build
```

The app service builds the working tree rather than a pinned ref, so the stack runs whatever is checked out — uncommitted edits included. Day-to-day work lands on the `dev` branch, which is why the snippet switches to it first; `master` only receives explicitly requested pushes.

That's it — visiting `http://localhost:8000` redirects straight into a working login. The `akadmin` password is `dev-insecure-akadmin-password` if you want to poke around the Authentik admin UI at `http://authentik-server:9000`.

**This file's secrets are hardcoded, non-random, dev-only placeholders on purpose** — safe to commit, safe to share, and clearly named so they can't be mistaken for something real (`dev-insecure-...`). Never reuse any value from it for a real or shared deployment; use the regular `docker-compose.yml` + the "Authentication setup" section above for that. It's a full standalone duplicate of `docker-compose.yml` (not an override layer) with its own volume names, so both stacks can coexist on the same machine without colliding — bring one down (`docker compose [-f docker-compose.dev.yml] down`) before starting the other if you're switching between them, since they both publish the same host ports (8000, 9000, 9443).

## Configuration

All configuration is via environment variables (see `app/config.py`), settable either natively or in `docker-compose.yml`:

| Variable | Default | Purpose |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `small.en` | faster-whisper model size (e.g. `base.en`, `medium.en`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | CTranslate2 compute type |
| `PRONUNCIATION_COACH_DATA_DIR` | `./data` | Root directory for the SQLite DB, saved recordings, and model/nltk caches |
| `HOST_UID` / `HOST_GID` | `1000` / `1000` | Docker only — UID/GID the container runs as, so bind-mounted files match your host user |
| `SESSION_SECRET_KEY` | *(required, no default)* | Signs this app's own login session cookie — distinct from Authentik's own secret |
| `AUTHENTIK_ISSUER` | *(required, no default)* | OIDC issuer URL of the Authentik Application, e.g. `http://authentik-server:9000/application/o/pronunciation-coach/` |
| `AUTHENTIK_CLIENT_ID` / `AUTHENTIK_CLIENT_SECRET` | *(required, no default)* | OAuth2 client credentials from the Authentik Provider |
| `AUTHENTIK_SECRET_KEY` | *(required, no default)* | Authentik's own internal secret key (its service, not ours) |
| `AUTHENTIK_PG_PASSWORD` | *(required, no default)* | Password for Authentik's own Postgres database (its service, not ours) |

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
├── auth.py            # OIDC client, get_current_user/require_web_session, User upsert
├── models.py            # Phrase, Attempt, User, UserPreference table models
├── schemas.py             # API request/response models
├── seed_data.py             # built-in practice phrases
├── ml.py                     # Whisper + G2p model loading
├── scoring.py                 # phoneme alignment & scoring algorithm
├── routers/                    # /api/phrases, /api/attempts, /auth/*, /api/me[/preferences]
└── tests/                        # pytest suite
frontend/
├── index.html
├── app.js            # recording, submission, results rendering
└── style.css
Dockerfile
docker-compose.yml
docker-compose.dev.yml   # standalone dev stack, Authentik auto-configured
authentik-blueprints/
└── pronunciation-coach.yaml   # declarative OIDC Provider + Application for the dev stack
```

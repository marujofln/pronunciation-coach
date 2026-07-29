import os
from pathlib import Path

from sqlalchemy import URL

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PRONUNCIATION_COACH_DATA_DIR", BASE_DIR / "data"))
AUDIO_DIR = DATA_DIR / "audio"
WHISPER_MODEL_DIR = DATA_DIR / "whisper_models"
NLTK_DATA_DIR = DATA_DIR / "nltk_data"

# Must happen before anything imports nltk / g2p_en, so their data lookups and
# downloads stay confined to our gitignored data dir instead of ~/nltk_data.
os.environ.setdefault("NLTK_DATA", str(NLTK_DATA_DIR))

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small.en")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


def _database_url() -> str:
    """The Postgres URL: assembled from discrete env vars, or handed over whole.

    DATABASE_URL wins outright when set — it's the escape hatch for a managed
    database, a unix socket, or connection query params the discrete vars can't
    express, and it's how the test suite points the app at its throwaway
    container. Otherwise the URL is built with URL.create() rather than an
    f-string, so a password containing ':', '@', '/' or '?' gets percent-encoded
    instead of silently corrupting the URL.
    """
    if url := os.environ.get("DATABASE_URL"):
        return url
    return URL.create(
        drivername="postgresql+psycopg",
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "pronunciation_coach"),
        username=os.environ.get("POSTGRES_USER", "pronunciation_coach"),
        # Security-sensitive: no default. Fail loudly rather than fall back to
        # something guessable. Only reached on this branch, so a
        # DATABASE_URL-driven run (the test suite, a managed database) never
        # needs it.
        password=os.environ["POSTGRES_PASSWORD"],
    ).render_as_string(hide_password=False)


DATABASE_URL = _database_url()

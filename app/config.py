import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PRONUNCIATION_COACH_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "pronunciation_coach.db"
AUDIO_DIR = DATA_DIR / "audio"
WHISPER_MODEL_DIR = DATA_DIR / "whisper_models"
NLTK_DATA_DIR = DATA_DIR / "nltk_data"

# Must happen before anything imports nltk / g2p_en, so their data lookups and
# downloads stay confined to our gitignored data dir instead of ~/nltk_data.
os.environ.setdefault("NLTK_DATA", str(NLTK_DATA_DIR))

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small.en")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

# Security-sensitive: no defaults. Fail loudly rather than run with an
# insecure/empty session secret or a misconfigured OIDC client.
AUTHENTIK_ISSUER = os.environ["AUTHENTIK_ISSUER"]
AUTHENTIK_CLIENT_ID = os.environ["AUTHENTIK_CLIENT_ID"]
AUTHENTIK_CLIENT_SECRET = os.environ["AUTHENTIK_CLIENT_SECRET"]
SESSION_SECRET_KEY = os.environ["SESSION_SECRET_KEY"]

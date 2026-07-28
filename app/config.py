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

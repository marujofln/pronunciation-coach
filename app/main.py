from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app import config
from app.db import engine
from app.ml import load_g2p, load_whisper_model
from app.routers.attempts import router as attempts_router
from app.routers.phrases import router as phrases_router
from app.seed_data import seed_phrases


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    config.WHISPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    config.NLTK_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # No create_all() here: the schema belongs to Alembic and is applied
    # explicitly (`uv run alembic upgrade head`, or the migrate service in
    # Docker), so a bad migration fails on its own instead of crash-looping the
    # app on boot. Seeding stays — the phrase list is data the app owns, it's
    # idempotent, and it reconciles drifted rows on every start.
    with Session(engine) as session:
        seed_phrases(session)

    app.state.g2p = load_g2p()
    app.state.whisper_model = load_whisper_model()
    yield


app = FastAPI(lifespan=lifespan, title="Pronunciation Coach")

app.include_router(phrases_router)
app.include_router(attempts_router)

# Mounted last, after the API routers: this is a low-priority static route that
# only matches once nothing else has, so it can never shadow /api/*.
app.frontend("/", directory=str(config.BASE_DIR / "frontend"))

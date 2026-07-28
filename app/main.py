from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session, SQLModel
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.auth import WebAuthRequired, redirect_to_login, require_web_session
from app.db import engine
from app.ml import load_g2p, load_whisper_model
from app.routers.attempts import router as attempts_router
from app.routers.auth import router as auth_router
from app.routers.phrases import router as phrases_router
from app.seed_data import seed_phrases


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    config.WHISPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    config.NLTK_DATA_DIR.mkdir(parents=True, exist_ok=True)

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_phrases(session)

    app.state.g2p = load_g2p()
    app.state.whisper_model = load_whisper_model()
    yield


app = FastAPI(lifespan=lifespan, title="Pronunciation Coach")
app.add_middleware(
    SessionMiddleware, secret_key=config.SESSION_SECRET_KEY, same_site="lax"
)
app.add_exception_handler(WebAuthRequired, redirect_to_login)

app.include_router(phrases_router)
app.include_router(attempts_router)
app.include_router(auth_router)

frontend_router = APIRouter(dependencies=[Depends(require_web_session)])
frontend_router.frontend("/", directory=str(config.BASE_DIR / "frontend"))
app.include_router(frontend_router)

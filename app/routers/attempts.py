from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from sqlmodel import select

from app import config
from app.auth import CurrentUserDep
from app.db import SessionDep
from app.ml import G2pDep, WhisperModelDep, transcribe_audio
from app.models import Attempt, Phrase
from app.schemas import AttemptRead, AttemptResult, PhraseStats, StatsRead, WordFeedback
from app.scoring import score_attempt

router = APIRouter(prefix="/api/attempts", tags=["attempts"])

_CONTENT_TYPE_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
}


def _ext_from_content_type(content_type: str | None) -> str:
    return _CONTENT_TYPE_EXTENSIONS.get(content_type or "", ".bin")


@router.post("/")
def submit_attempt(
    session: SessionDep,
    whisper_model: WhisperModelDep,
    g2p: G2pDep,
    current_user: CurrentUserDep,
    phrase_id: Annotated[int, Form()],
    audio: Annotated[UploadFile, File()],
) -> AttemptResult:
    phrase = session.get(Phrase, phrase_id)
    if phrase is None:
        raise HTTPException(status_code=404, detail="Phrase not found")

    audio_bytes = audio.file.read()
    ext = _ext_from_content_type(audio.content_type)
    audio_path = config.AUDIO_DIR / f"{uuid4()}{ext}"
    audio_path.write_bytes(audio_bytes)

    transcript = transcribe_audio(whisper_model, audio_path)
    score, word_feedback = score_attempt(phrase.text, transcript, g2p)

    attempt = Attempt(
        phrase_id=phrase.id,
        user_id=current_user.id,
        transcript=transcript,
        score=score,
        word_feedback=[wf.model_dump() for wf in word_feedback],
        audio_path=str(audio_path),
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    return AttemptResult(
        attempt_id=attempt.id,
        phrase_id=phrase.id,
        phrase_text=phrase.text,
        transcript=transcript,
        score=score,
        word_feedback=word_feedback,
        created_at=attempt.created_at,
    )


@router.get("/")
def list_attempts(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(le=200)] = 50,
    phrase_id: Annotated[int | None, Query()] = None,
) -> list[AttemptRead]:
    query = (
        select(Attempt)
        .where(Attempt.user_id == current_user.id)
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    )
    if phrase_id is not None:
        query = query.where(Attempt.phrase_id == phrase_id)
    attempts = session.exec(query).all()
    return [
        AttemptRead(
            id=a.id,
            phrase_id=a.phrase_id,
            phrase_text=a.phrase.text if a.phrase else "",
            transcript=a.transcript,
            score=a.score,
            word_feedback=[WordFeedback(**wf) for wf in a.word_feedback],
            created_at=a.created_at,
        )
        for a in attempts
    ]


@router.get("/stats")
def get_attempt_stats(session: SessionDep, current_user: CurrentUserDep) -> StatsRead:
    attempts = session.exec(
        select(Attempt).where(Attempt.user_id == current_user.id)
    ).all()
    total_attempts = len(attempts)
    average_score = (
        round(sum(a.score for a in attempts) / total_attempts, 1)
        if total_attempts
        else None
    )

    by_phrase: dict[int, list[Attempt]] = {}
    for a in attempts:
        by_phrase.setdefault(a.phrase_id, []).append(a)

    per_phrase = [
        PhraseStats(
            phrase_id=phrase_id,
            phrase_text=phrase_attempts[0].phrase.text
            if phrase_attempts[0].phrase
            else "",
            attempts=len(phrase_attempts),
            average_score=round(
                sum(a.score for a in phrase_attempts) / len(phrase_attempts), 1
            ),
        )
        for phrase_id, phrase_attempts in by_phrase.items()
    ]
    per_phrase.sort(key=lambda p: p.average_score, reverse=True)

    return StatsRead(
        total_attempts=total_attempts,
        average_score=average_score,
        per_phrase=per_phrase,
    )

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import select

from app.auth import get_current_user
from app.db import SessionDep
from app.models import Difficulty, Phrase
from app.schemas import PhraseRead

router = APIRouter(
    prefix="/api/phrases",
    tags=["phrases"],
    dependencies=[Depends(get_current_user)],
)


def _filtered_query(
    difficulty: Difficulty | None,
    category: str | None,
):
    query = select(Phrase)
    if difficulty is not None:
        query = query.where(Phrase.difficulty == difficulty)
    if category is not None:
        query = query.where(Phrase.category == category)
    return query


@router.get("/")
def list_phrases(
    session: SessionDep,
    difficulty: Annotated[Difficulty | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> list[PhraseRead]:
    query = _filtered_query(difficulty, category).order_by(Phrase.id)
    phrases = session.exec(query).all()
    return [PhraseRead.model_validate(p, from_attributes=True) for p in phrases]


@router.get("/random")
def get_random_phrase(
    session: SessionDep,
    difficulty: Annotated[Difficulty | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> PhraseRead:
    query = _filtered_query(difficulty, category).order_by(func.random()).limit(1)
    phrase = session.exec(query).first()
    if phrase is None:
        raise HTTPException(
            status_code=404, detail="No phrase matches the given filters"
        )
    return PhraseRead.model_validate(phrase, from_attributes=True)

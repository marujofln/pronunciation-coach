from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import Difficulty


class WordFeedback(BaseModel):
    position: int
    expected_word: str | None = None
    heard_word: str | None = None
    expected_phonemes: list[str] = Field(default_factory=list)
    heard_phonemes: list[str] = Field(default_factory=list)
    status: Literal["correct", "mispronounced", "missing", "extra"]
    word_score: float | None = None


class PhraseRead(BaseModel):
    id: int
    text: str
    difficulty: Difficulty
    category: str | None
    created_at: datetime


class AttemptRead(BaseModel):
    id: int
    phrase_id: int
    phrase_text: str
    transcript: str
    score: float
    word_feedback: list[WordFeedback]
    created_at: datetime


class AttemptResult(BaseModel):
    attempt_id: int
    phrase_id: int
    phrase_text: str
    transcript: str
    score: float
    word_feedback: list[WordFeedback]
    created_at: datetime


class PhraseStats(BaseModel):
    phrase_id: int
    phrase_text: str
    attempts: int
    average_score: float


class StatsRead(BaseModel):
    total_attempts: int
    average_score: float | None
    per_phrase: list[PhraseStats]

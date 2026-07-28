from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Phrase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    text: str = Field(index=True, unique=True)
    difficulty: Difficulty = Field(index=True)
    category: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    attempts: list["Attempt"] = Relationship(back_populates="phrase")


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sub: str = Field(index=True, unique=True)
    email: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    attempts: list["Attempt"] = Relationship(back_populates="user")


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    phrase_id: int = Field(foreign_key="phrase.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    transcript: str
    score: float
    word_feedback: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    audio_path: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)

    phrase: Phrase | None = Relationship(back_populates="attempts")
    user: User | None = Relationship(back_populates="attempts")

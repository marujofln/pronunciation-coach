from datetime import UTC, datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


# VARCHAR plus a Python-side enum, not a native Postgres ENUM type: adding or
# renaming a difficulty would otherwise need ALTER TYPE ... ADD VALUE (which
# historically cannot run inside a transaction) on the way up and a hand-written
# DROP TYPE on the way down, since Alembic's autogenerate emits neither.
# native_enum=False makes that an ordinary column edit. create_constraint stays
# at SQLAlchemy's default of False, so no CHECK is emitted either — validating
# the value is Pydantic's job at the API boundary. A type instance is safe to
# share across columns.
DifficultyType = sa.Enum(Difficulty, native_enum=False)

# TIMESTAMPTZ, not TIMESTAMP. Every value written here is an aware UTC datetime,
# and psycopg3 adapts those with the timestamptz type OID; assigning that to a
# naive column is an implicit cast that Postgres runs through the session's
# TimeZone setting, so what actually got stored would depend on a GUC nobody
# thinks about.
UtcDateTime = sa.DateTime(timezone=True)


class Phrase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    text: str = Field(index=True, unique=True)
    difficulty: Difficulty = Field(index=True, sa_type=DifficultyType)
    category: str | None = Field(default=None, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )

    attempts: list["Attempt"] = Relationship(back_populates="phrase")


class User(SQLModel, table=True):
    # `user` is a reserved word in Postgres: SQLAlchemy quotes it correctly, but
    # every hand-written query and psql session then has to remember the quotes
    # (`SELECT * FROM user` is a syntax error, not a table scan).
    __tablename__ = "app_user"

    id: int | None = Field(default=None, primary_key=True)
    sub: str = Field(index=True, unique=True)
    email: str | None = Field(default=None, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )

    attempts: list["Attempt"] = Relationship(back_populates="user")


class UserPreference(SQLModel, table=True):
    """One row per user, holding the filter selection to restore on their next visit.

    Both fields are nullable because "Any" is a real choice, not a missing one.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", index=True, unique=True)
    difficulty: Difficulty | None = Field(default=None, sa_type=DifficultyType)
    category: str | None = Field(default=None)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), sa_type=UtcDateTime
    )


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    phrase_id: int = Field(foreign_key="phrase.id", index=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    transcript: str
    score: float
    # JSONB, not the generic sa.JSON: on Postgres that compiles to `json`, which
    # re-parses the text on every read and has no `=` operator, so any future
    # WHERE/DISTINCT over this column would simply error. Keep the sa_column=
    # form rather than sa_type= — the two aren't equivalent, sa_column bypasses
    # SQLModel's column inference and keeps the shape explicit.
    word_feedback: list[dict] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    audio_path: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), index=True, sa_type=UtcDateTime
    )

    phrase: Phrase | None = Relationship(back_populates="attempts")
    user: User | None = Relationship(back_populates="attempts")

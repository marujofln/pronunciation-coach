from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, create_engine

from app import config

# pool_pre_ping: unlike a SQLite file, a Postgres server drops pooled
# connections out from under us (container restart, idle_session_timeout,
# `docker compose restart`). Without the pre-ping the first request after that
# fails with a stale-connection error instead of transparently reconnecting.
# timezone=utc: every timestamp column is TIMESTAMPTZ, so pinning the session
# timezone keeps the offsets the API serializes independent of whatever the
# server's own TimeZone setting happens to be.
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=utc"},
)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

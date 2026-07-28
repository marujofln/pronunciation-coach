from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, create_engine

from app import config

engine = create_engine(
    f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False}
)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

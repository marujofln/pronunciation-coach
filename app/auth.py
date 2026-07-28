from typing import Annotated
from urllib.parse import quote

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select
from starlette.responses import RedirectResponse

from app import config
from app.db import SessionDep
from app.models import User

oauth = OAuth()
oauth.register(
    name="authentik",
    server_metadata_url=config.AUTHENTIK_ISSUER.rstrip("/")
    + "/.well-known/openid-configuration",
    client_id=config.AUTHENTIK_CLIENT_ID,
    client_secret=config.AUTHENTIK_CLIENT_SECRET,
    client_kwargs={"scope": "openid profile email"},
)


class WebAuthRequired(Exception):
    def __init__(self, next_path: str) -> None:
        self.next_path = next_path


async def redirect_to_login(request: Request, exc: WebAuthRequired) -> RedirectResponse:
    return RedirectResponse(
        url=f"/auth/login?next={quote(exc.next_path)}", status_code=302
    )


def get_or_create_user(session: Session, *, sub: str, email: str | None) -> User:
    user = session.exec(select(User).where(User.sub == sub)).first()
    if user is None:
        user = User(sub=sub, email=email)
        session.add(user)
        session.commit()
        session.refresh(user)
    elif email is not None and user.email != email:
        user.email = email
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def _user_from_session(request: Request, session: Session) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    user = session.get(User, user_id)
    if user is None:
        request.session.clear()
    return user


def get_current_user(request: Request, session: SessionDep) -> User:
    user = _user_from_session(request, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_web_session(request: Request, session: SessionDep) -> User:
    user = _user_from_session(request, session)
    if user is None:
        raise WebAuthRequired(next_path=request.url.path)
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]

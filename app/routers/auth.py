from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from app.auth import CurrentUserDep, get_or_create_user, oauth
from app.db import SessionDep
from app.schemas import UserRead

router = APIRouter(tags=["auth"])


def _safe_next_path(raw: str | None) -> str:
    if not raw or not raw.startswith("/") or raw.startswith("//"):
        return "/"
    return raw


@router.get("/auth/login")
async def login(request: Request, next: str | None = None) -> RedirectResponse:
    request.session["post_login_redirect"] = _safe_next_path(next)
    redirect_uri = request.url_for("auth_callback")
    return await oauth.authentik.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def callback(request: Request, session: SessionDep) -> RedirectResponse:
    token = await oauth.authentik.authorize_access_token(request)
    userinfo = token["userinfo"]
    user = get_or_create_user(session, sub=userinfo["sub"], email=userinfo.get("email"))
    request.session["user_id"] = user.id
    next_path = request.session.pop("post_login_redirect", "/")
    return RedirectResponse(url=next_path)


@router.get("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/")


@router.get("/api/me")
def read_current_user(current_user: CurrentUserDep) -> UserRead:
    return UserRead(id=current_user.id, email=current_user.email)

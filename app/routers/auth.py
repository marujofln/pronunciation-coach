from urllib.parse import urlencode

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
    # Kept only to pass back as logout's id_token_hint. The session cookie is
    # signed and httponly, so this still never reaches browser JS.
    if id_token := token.get("id_token"):
        request.session["id_token"] = id_token
    next_path = request.session.pop("post_login_redirect", "/")
    return RedirectResponse(url=next_path)


async def _end_session_url(request: Request, id_token: str | None) -> str:
    """Authentik's RP-initiated logout URL, or "/" if it can't be resolved.

    Dropping our own session cookie is not enough on its own: Authentik keeps
    a separate session, so the redirect to /auth/login would be silently
    re-authorized and land the user straight back in a logged-in app, making
    Logout look like it did nothing. Ending the IdP session is what makes it
    stick.
    """
    try:
        metadata = await oauth.authentik.load_server_metadata()
    except Exception:  # noqa: BLE001
        # Deliberately broad: metadata is fetched over the network, and a
        # logout that 500s because the IdP is unreachable is worse than one
        # that only clears the local session (already done by the caller).
        # Narrowing this to httpx/OSError would let an unanticipated error
        # type break the very path this fallback exists to protect.
        return "/"

    endpoint = metadata.get("end_session_endpoint")
    if not endpoint:
        return "/"

    params = {"post_logout_redirect_uri": str(request.base_url)}
    if id_token:
        # Without the hint Authentik interrupts logout with a confirmation page.
        params["id_token_hint"] = id_token
    return f"{endpoint}?{urlencode(params)}"


@router.get("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    id_token = request.session.get("id_token")
    request.session.clear()
    return RedirectResponse(url=await _end_session_url(request, id_token))


@router.get("/api/me")
def read_current_user(current_user: CurrentUserDep) -> UserRead:
    return UserRead(id=current_user.id, email=current_user.email)

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlmodel import Session, select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.models import UserPreference
from app.schemas import PreferencesRead, PreferencesUpdate

router = APIRouter(prefix="/api/me", tags=["preferences"])


def _preference_for(session: Session, user_id: int) -> UserPreference | None:
    return session.exec(
        select(UserPreference).where(UserPreference.user_id == user_id)
    ).first()


@router.get("/preferences")
def read_preferences(
    session: SessionDep, current_user: CurrentUserDep
) -> PreferencesRead:
    preference = _preference_for(session, current_user.id)
    if preference is None:
        # A user who has never chosen anything gets the same "Any/Any" shape as
        # one who explicitly chose it, so the frontend needs no special case.
        return PreferencesRead(difficulty=None, category=None)
    return PreferencesRead(
        difficulty=preference.difficulty, category=preference.category
    )


@router.put("/preferences")
def update_preferences(
    session: SessionDep, current_user: CurrentUserDep, update: PreferencesUpdate
) -> PreferencesRead:
    preference = _preference_for(session, current_user.id)
    if preference is None:
        preference = UserPreference(user_id=current_user.id)

    preference.difficulty = update.difficulty
    # An HTML <select> sends "" for its "Any" option; store that as no filter
    # rather than as a category no phrase will ever match.
    preference.category = update.category or None
    preference.updated_at = datetime.now(UTC)

    session.add(preference)
    session.commit()
    session.refresh(preference)

    return PreferencesRead(
        difficulty=preference.difficulty, category=preference.category
    )

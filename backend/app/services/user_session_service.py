"""
Authenticated session lifecycle (V3 Milestone 1 Phase 2): creating a
new session for a just-authenticated user, validating/looking up an
existing one, and sliding its inactivity expiry forward on activity.

Deliberately mirrors guest_session_service.py function-for-function --
same shape, same "service layer is where the actual logic and its
tests live, deps.py stays thin on top of it" convention (see that
file's own docstring) -- extended for the two real differences between
a guest and an authenticated session: this one carries a `user_id`,
and its inactivity window (`user_session_inactivity_days`) is measured
in days, not minutes, since staying signed in across a normal return
visit is the entire point of an authenticated session (see that
setting's docstring in core/config.py).
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UserSession


def _assume_utc(value: datetime) -> datetime:
    """
    Reattaches the UTC-ness SQLite silently drops from every timestamp
    this backend writes. Same issue, same fix, as
    guest_session_service.py's `_assume_utc` (see that docstring, and
    schemas/conversation.py's, for the full explanation) -- needed
    here for the same reason: this module compares these timestamps
    against a timezone-aware `datetime.now(timezone.utc)` to decide
    expiry.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def generate_session_token() -> str:
    """
    A fresh, unpredictable authenticated-session id. Identical
    reasoning and implementation to
    guest_session_service.generate_session_token -- this is a bearer
    credential (see UserSession's docstring in db/models.py), not a
    plain resource id, so it gets `secrets.token_urlsafe(32)` (256
    bits of CSPRNG randomness) rather than `db.models.generate_uuid()`.
    Not shared as one function between the two session types only
    because guest_session_service.py is Phase 1's file and this phase
    was told to extend, not restructure, what it built -- the two
    implementations are intentionally identical.
    """
    return secrets.token_urlsafe(32)


def create_user_session(db: Session, user_id: str) -> UserSession:
    """
    Mints a brand new authenticated session for `user_id` and persists
    it immediately, for the same reason
    guest_session_service.create_guest_session does: the id this
    returns must be valid for the very next request that presents it,
    because it's handed back to the caller (see routes_auth.py) to set
    as a cookie in the same request/response cycle that created it.
    """
    now = datetime.now(timezone.utc)
    session = UserSession(
        id=generate_session_token(),
        user_id=user_id,
        created_at=now,
        last_seen_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_valid_user_session(db: Session, token: str) -> UserSession | None:
    """
    Looks up `token` and returns its UserSession only if it exists,
    hasn't been revoked, and hasn't expired from inactivity -- None in
    every other case, including "no such session ever existed".
    Identical "caller can't tell those apart, on purpose" reasoning as
    guest_session_service.get_valid_guest_session.
    """
    if not token:
        return None

    session = (
        db.query(UserSession)
        .filter(UserSession.id == token, UserSession.revoked_at.is_(None))
        .first()
    )
    if session is None:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.user_session_inactivity_days
    )
    if _assume_utc(session.last_seen_at) < cutoff:
        return None

    return session


def touch_user_session(db: Session, session: UserSession) -> None:
    """
    Records activity on an already-valid authenticated session,
    sliding its inactivity-expiry window forward -- called on every
    request that resolves to this session (see
    app/api/deps.py:get_current_identity), same as
    guest_session_service.touch_guest_session.
    """
    session.last_seen_at = datetime.now(timezone.utc)
    db.commit()


def delete_user_session(db: Session, token: str) -> None:
    """
    Removes an authenticated-session row outright. Used both for
    logout (see routes_auth.py) -- the whole point being that this
    same token must never resolve to a valid session again -- and for
    a request presenting a cookie whose session has already expired or
    never existed (see api/deps.py), matching
    guest_session_service.delete_guest_session's lazy,
    encounter-driven cleanup rather than a scheduled reaper.
    """
    db.query(UserSession).filter(UserSession.id == token).delete()
    db.commit()

"""
Guest session lifecycle (V3 Milestone 1 Phase 1): creating a new guest
session, validating/looking up an existing one, and sliding its
inactivity expiry forward on activity.

This is the service layer app/api/deps.py:get_current_identity is thin
on top of -- matching this project's existing convention (see e.g.
routes_summary.py delegating to summary_service.py) of keeping request
handling/dependency wiring thin and putting the actual logic here,
where it's directly unit-testable without going through a live HTTP
request.
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import GuestSession


def _assume_utc(value: datetime) -> datetime:
    """
    Reattaches the UTC-ness SQLite silently drops from every timestamp
    this backend writes. Same issue, same fix, as
    app/schemas/conversation.py's `_assume_utc` (see that docstring for
    the full explanation) -- needed here because, unlike that file,
    this module actually compares these timestamps against a
    timezone-aware `datetime.now(timezone.utc)` to decide expiry, and
    comparing an aware and a naive datetime raises TypeError rather
    than just being wrong.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def generate_session_token() -> str:
    """
    A fresh, unpredictable guest session id.

    Deliberately not `db.models.generate_uuid()`, even though a UUID4
    is also drawn from `os.urandom` and would be hard to guess: that
    helper names *what* it makes (an id), and every other call site
    uses its output as a non-secret resource identifier -- fine to log,
    put in a URL, or show in an error message. This value is the
    opposite: it's a bearer credential (see GuestSession's docstring in
    db/models.py -- holding it *is* being this guest), so it gets its
    own function that says so, and every call site should treat it
    like a password: never logged, only ever transported in the
    httponly cookie it's issued in.

    `secrets.token_urlsafe(32)` gives 256 bits of CSPRNG randomness,
    URL-safe base64-encoded -- comfortably unguessable, and using the
    stdlib's `secrets` module (built exactly for "generate a security
    token") rather than `uuid`/`random` needs no new dependency and
    signals the intent directly to anyone reading this file.
    """
    return secrets.token_urlsafe(32)


def create_guest_session(db: Session) -> GuestSession:
    """
    Mints a brand new guest session and persists it immediately (not
    just constructed and left pending) so the id this returns is
    guaranteed valid for the very next request that presents it --
    matters here because the id is handed back to the caller (see
    app/api/deps.py) to set as a cookie in the same request/response
    cycle that created it.
    """
    now = datetime.now(timezone.utc)
    session = GuestSession(id=generate_session_token(), created_at=now, last_seen_at=now)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_valid_guest_session(db: Session, token: str) -> GuestSession | None:
    """
    Looks up `token` and returns its GuestSession only if it exists,
    hasn't been revoked, and hasn't expired from inactivity -- None in
    every other case, including "no such session ever existed". The
    caller can't tell those apart from this return value alone, on
    purpose: from the outside, an expired guest session and one that
    never existed should be indistinguishable, the same way a real
    login session behaves once it's expired.
    """
    if not token:
        return None

    session = (
        db.query(GuestSession)
        .filter(GuestSession.id == token, GuestSession.revoked_at.is_(None))
        .first()
    )
    if session is None:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.guest_session_inactivity_minutes
    )
    if _assume_utc(session.last_seen_at) < cutoff:
        return None

    return session


def touch_guest_session(db: Session, session: GuestSession) -> None:
    """
    Records activity on an already-valid guest session, sliding its
    inactivity-expiry window forward. Called on every request that
    resolves to this session (see app/api/deps.py:get_current_identity)
    -- normal navigation and API use is exactly the "meaningful
    activity" this phase's brief asks to keep a session alive, so no
    separate heartbeat/keep-alive endpoint or extra request is needed
    for this.
    """
    session.last_seen_at = datetime.now(timezone.utc)
    db.commit()


def delete_guest_session(db: Session, token: str) -> None:
    """
    Removes a guest session row outright. Used when a request presents
    a cookie whose session has already expired or never existed (see
    app/api/deps.py) -- rather than let a dead row linger indefinitely,
    it's cleared the moment it's next encountered. This is a lazy,
    encounter-driven cleanup, not a scheduled sweep of every expired
    session in the table; this app has no background job runner yet,
    and a session nobody ever presents again is inert (unreachable,
    and -- per this phase's ownership scope -- not yet attached to any
    other data) whether or not its row still exists. A periodic reaper
    would be worth adding once guest data actually hangs off this
    table (Milestone 2) and idle rows are worth reclaiming proactively.
    """
    db.query(GuestSession).filter(GuestSession.id == token).delete()
    db.commit()

"""
Request-scoped dependencies shared across API routes.

`get_current_identity` is the single integration point that answers
"who is making this request?" (V3 Milestone 1 Phase 1's north-star
goal -- see the phase brief). It's wired in once, centrally, at router
registration (see app/main.py), rather than each route file
implementing its own ad-hoc "is there a guest cookie?" check -- exactly
the thing this phase's brief says to avoid.

For this phase, this always resolves to a guest identity: reusing the
caller's existing guest session (and sliding its inactivity expiry
forward) if their request carries a valid one, or minting a new one
and issuing it as a cookie if not. Milestone 1 Phase 2 (account
authentication) will extend this to check for an authenticated session
first and fall back to guest only when one isn't present. Everything
that depends on `Identity` -- today, just this dependency's callers --
is written against that abstraction, not against "guest" specifically,
so that extension is additive here rather than a rework of every call
site.
"""

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.schemas.identity import Identity, IdentityType
from app.services import guest_session_service


def _set_guest_session_cookie(response: Response, token: str) -> None:
    """
    Issues/refreshes the guest session cookie on `response`.

    Called on every request that resolves an identity (both when a new
    session was just created and when an existing one was just
    touched) so the cookie's own `max_age` slides forward in lockstep
    with the server-side inactivity window `touch_guest_session`
    extends (app/services/guest_session_service.py) -- otherwise the
    cookie could expire client-side before the server-side session
    would, silently starting a new guest identity mid-session for
    anyone active for longer than one fixed cookie lifetime.

    `httponly=True` unconditionally: nothing in the frontend needs (or
    should have) direct JS access to this value -- it's a bearer
    credential (see GuestSession's docstring in db/models.py), and
    keeping it out of `document.cookie` is a cheap, real reduction in
    XSS blast radius. `secure`/`samesite` come from settings rather
    than being hardcoded, so a production deployment can tighten them
    (see the settings' own docstrings in core/config.py) without a
    code change.
    """
    response.set_cookie(
        key=settings.guest_session_cookie_name,
        value=token,
        max_age=settings.guest_session_inactivity_minutes * 60,
        httponly=True,
        secure=settings.guest_session_cookie_secure,
        samesite=settings.guest_session_cookie_samesite,
        path="/",
    )


def get_current_identity(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Identity:
    """
    Resolves the current request's Identity, creating a new guest
    session (and issuing its cookie) if the request doesn't carry a
    still-valid one.

    Takes `response` -- not just `request` -- because resolving
    identity can itself have a side effect the caller needs reflected
    in what gets sent back: a brand new or freshly-touched session's
    cookie. FastAPI dependencies can mutate the eventual response this
    way (it's the same `Response` instance the route handler's return
    value gets rendered into), which is what lets this stay a plain
    dependency rather than needing ASGI middleware to reach the
    outgoing response.
    """
    token = request.cookies.get(settings.guest_session_cookie_name)
    session = guest_session_service.get_valid_guest_session(db, token) if token else None

    if session is None:
        if token:
            # The cookie pointed at a session that's expired or never
            # existed (e.g. a stale cookie surviving a dev DB reset).
            # Clear out the row if one is still there before minting a
            # replacement, rather than leave it as unreachable dead
            # data indefinitely.
            guest_session_service.delete_guest_session(db, token)
        session = guest_session_service.create_guest_session(db)
    else:
        guest_session_service.touch_guest_session(db, session)

    _set_guest_session_cookie(response, session.id)

    return Identity(type=IdentityType.GUEST, id=session.id)

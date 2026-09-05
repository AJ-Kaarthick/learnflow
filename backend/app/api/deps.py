"""
Request-scoped dependencies shared across API routes.

`get_current_identity` is the single integration point that answers
"who is making this request?" (V3 Milestone 1 Phase 1's north-star
goal -- see the phase brief). It's wired in once, centrally, at router
registration (see app/main.py), rather than each route file
implementing its own ad-hoc "is there a guest cookie?" check -- exactly
the thing this phase's brief says to avoid.

Phase 1 always resolved this to a guest identity. V3 Milestone 1
Phase 2 (account authentication) extends it, exactly as this
docstring previously said it would: a request carrying a valid
authenticated session cookie now resolves to that USER identity, and
guest resolution (unchanged from Phase 1, below) only runs as the
fallback when no valid authenticated session is presented. Everything
that depends on `Identity` was already written against that
abstraction, not against "guest" specifically, so this extension is
additive here rather than a rework of every call site.
"""

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User
from app.schemas.identity import Identity, IdentityType
from app.services import guest_session_service, user_session_service


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


def set_user_session_cookie(response: Response, token: str) -> None:
    """
    Issues/refreshes the authenticated session cookie on `response`.
    Same reasoning as `_set_guest_session_cookie` throughout --
    `max_age` slides forward with `user_session_inactivity_days` (see
    user_session_service.touch_user_session), and `httponly=True`
    unconditionally for the same "this is a bearer credential, not
    something the frontend should ever read via `document.cookie`"
    reason (see UserSession's docstring in db/models.py).

    Deliberately reuses `guest_session_cookie_secure`/`_samesite`
    rather than introducing a second, parallel pair of settings: those
    two values encode a fact about the deployment itself (is it served
    over HTTPS, are frontend and backend on the same site?), not
    anything specific to guest sessions -- there is exactly one
    correct answer for "should any of this app's cookies require
    HTTPS" in a given environment, so one production `.env` change
    (e.g. GUEST_SESSION_COOKIE_SECURE=true) correctly tightens both
    cookies at once instead of needing to remember to update two.

    Not underscore-prefixed, unlike `_set_guest_session_cookie` above:
    this one is also called directly from routes_auth.py (signup and
    signin issue the very first cookie for a session, before this
    dependency ever runs), so it's a real part of this module's public
    surface, not purely a `get_current_identity` implementation
    detail. `clear_user_session_cookie`, below, is public for the same
    reason.
    """
    response.set_cookie(
        key=settings.user_session_cookie_name,
        value=token,
        max_age=settings.user_session_inactivity_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.guest_session_cookie_secure,
        samesite=settings.guest_session_cookie_samesite,
        path="/",
    )


def clear_user_session_cookie(response: Response) -> None:
    """
    Removes the authenticated session cookie from the browser. Used
    both when a presented user-session cookie turns out to be
    invalid/expired (get_current_identity, below) and on explicit
    logout (routes_auth.py) -- `path="/"` must match the path the
    cookie was originally set with (see set_user_session_cookie) or
    the browser treats this as clearing a different cookie entirely.
    """
    response.delete_cookie(key=settings.user_session_cookie_name, path="/")


def _resolve_guest_identity(request: Request, response: Response, db: Session) -> Identity:
    """
    Phase 1's guest resolution, unchanged: reuse the caller's existing
    guest session (sliding its inactivity expiry forward) if their
    request carries a valid one, or mint a new one and issue it as a
    cookie if not. Extracted from get_current_identity's body as-is so
    that function's job is now just "check for an authenticated
    session first, then fall back to this" -- this function itself is
    identical to Phase 1's.
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


def get_current_identity(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Identity:
    """
    Resolves the current request's Identity.

    Checks for a valid authenticated session first (V3 Milestone 1
    Phase 2): if the request carries one, that user's identity wins,
    its session is touched (sliding its own expiry forward) and its
    cookie refreshed -- no guest session is looked up or created for
    this request at all, since it's already resolved to something more
    specific. Only when no valid authenticated session is presented
    does this fall back to Phase 1's guest resolution
    (_resolve_guest_identity, above) -- exactly the "check for an
    authenticated session first and fall back to guest only when one
    isn't present" extension this function's docstring described
    before this phase existed.

    A user-session cookie that doesn't resolve (expired, revoked, or
    simply garbage) is cleaned up here the same way a bad guest cookie
    already was in Phase 1 -- deleted server-side if a row still
    exists, and the cookie itself cleared from the response -- rather
    than silently falling through and leaving a dead cookie for every
    future request to keep re-checking.

    Takes `response` -- not just `request` -- for the same reason as
    Phase 1: resolving identity can have a side effect (a cookie) the
    caller needs reflected in what gets sent back, and FastAPI
    dependencies can mutate the eventual response this way.
    """
    user_token = request.cookies.get(settings.user_session_cookie_name)
    if user_token:
        user_session = user_session_service.get_valid_user_session(db, user_token)
        if user_session is not None:
            user_session_service.touch_user_session(db, user_session)
            set_user_session_cookie(response, user_session.id)
            user = db.query(User).filter(User.id == user_session.user_id).first()
            # A UserSession whose User row no longer exists shouldn't
            # be reachable in this phase (nothing deletes a User yet),
            # but if it ever happened, treat it the same as any other
            # unresolvable session below rather than returning an
            # Identity with a None email a caller might not expect.
            if user is not None:
                return Identity(type=IdentityType.USER, id=user.id, email=user.email)

        # The cookie pointed at a session that's expired, revoked, or
        # never existed. Clean up the row if one's still there (same
        # "lazy, encounter-driven cleanup" as guest sessions) and clear
        # the cookie itself before falling back to guest resolution --
        # otherwise this same dead cookie gets re-checked, and fail,
        # on every subsequent request.
        user_session_service.delete_user_session(db, user_token)
        clear_user_session_cookie(response)

    return _resolve_guest_identity(request, response, db)

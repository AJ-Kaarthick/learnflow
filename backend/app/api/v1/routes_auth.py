from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.requests import Request
from sqlalchemy.orm import Session

from app.api.deps import clear_user_session_cookie, set_user_session_cookie
from app.core.config import settings
from app.db.database import get_db
from app.schemas.auth import SigninRequest, SignupRequest
from app.schemas.identity import Identity, IdentityType
from app.services import auth_service, guest_migration_service, guest_session_service, user_session_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately NOT one of app/main.py's IDENTITY_AWARE_ROUTERS: these
# three routes establish or end an authenticated session themselves --
# running get_current_identity as a router-level dependency first
# would mint and set a guest-session cookie on every signup/signin/
# logout request even though its result is never used and is about to
# be superseded (signup/signin) or is irrelevant (logout). Each route
# below takes exactly the dependencies it needs instead.


def _start_authenticated_session(db: Session, response: Response, user_id: str, email: str) -> Identity:
    """
    Shared by signup and signin: both end with the same outcome --
    a brand new authenticated session for `user_id`, issued as a
    cookie, with the resulting Identity handed back to the frontend so
    it has "the authenticated identity/state needed" (per this phase's
    brief) without a second round trip to GET /identity/me.
    """
    session = user_session_service.create_user_session(db, user_id)
    set_user_session_cookie(response, session.id)
    return Identity(type=IdentityType.USER, id=user_id, email=email)


@router.post("/signup", response_model=Identity, status_code=201)
def signup(
    payload: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> Identity:
    """
    Registers a new account and immediately signs it in -- "establish
    an authenticated session after successful signup" per this phase's
    brief, since asking someone to sign in a second time right after
    they just supplied the exact same credentials would be pure
    friction with no security benefit.

    409s on a duplicate email (see EmailAlreadyRegisteredError) rather
    than 400 -- the request itself is well-formed, it's the current
    state of the `users` table that conflicts with it, which is what
    409 Conflict means. The detail message deliberately doesn't
    distinguish "this exact email" from any other validation failure
    in a way that would let a caller distinguish a real signup
    conflict from a guess -- it plainly states the account exists,
    which is unavoidable for a signup endpoint (unlike signin, there's
    no way to reject a duplicate registration without revealing the
    email is taken).

    V3 Milestone 1 Phase 3 -- guest->account migration: "guest access
    is an upgrade path, not a dead end." If this browser is carrying a
    still-*active* guest session when it signs up, everything that
    guest session owns (documents, conversations, and everything that
    hangs off them -- see guest_migration_service.migrate_guest_data_to_user's
    own docstring for exactly what "everything" covers and why) moves
    to the brand-new account, atomically, before the response goes
    out. `get_valid_guest_session` returns None for a missing,
    expired, or already-revoked cookie -- exactly the same check
    get_current_identity's own guest fallback would apply -- so an
    expired guest session is silently *not* migrated (its data stays
    subject to Phase 1's existing expiration handling) rather than
    resurrected, and a browser with no guest cookie at all simply skips
    this block and signs up normally, same as before this phase
    existed.

    Deliberately does not run get_current_identity here (this router
    stays outside main.py's IDENTITY_AWARE_ROUTERS, per this file's own
    module comment) -- doing so would mint a brand-new guest session
    for a signup request that arrived with no guest cookie at all, and
    that brand-new session would then immediately become migration's
    *source* (owning nothing) instead of correctly doing nothing. Only
    a guest cookie that already resolves to a real, active session
    (checked read-only, via guest_session_service.get_valid_guest_session)
    ever triggers a migration.

    The now-migrated guest session's cookie is cleared from the
    response as routine cleanup, not because anything downstream
    depends on it being gone: get_current_identity always checks the
    authenticated-session cookie first (see that function's own
    docstring), so the freshly-issued user session below wins on every
    subsequent request regardless of whether a stale guest cookie is
    still sitting in the browser.
    """
    try:
        user = auth_service.create_user(db, payload.email, payload.password)
    except auth_service.EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    guest_token = request.cookies.get(settings.guest_session_cookie_name)
    guest_session = (
        guest_session_service.get_valid_guest_session(db, guest_token) if guest_token else None
    )
    if guest_session is not None:
        guest_migration_service.migrate_guest_data_to_user(db, guest_session.id, user.id)
        response.delete_cookie(key=settings.guest_session_cookie_name, path="/")

    return _start_authenticated_session(db, response, user.id, user.email)


@router.post("/signin", response_model=Identity)
def signin(payload: SigninRequest, response: Response, db: Session = Depends(get_db)) -> Identity:
    """
    Authenticates an existing account and establishes a session.

    A failed attempt -- wrong password or no such account -- always
    gets the same generic 401 with the same message, never a 404 or a
    message naming which part was wrong (see auth_service.authenticate_user's
    docstring): this phase's security requirement is to "avoid
    unnecessarily revealing whether an account exists", and a
    differently-worded or differently-coded response for "no such
    email" vs. "wrong password" would do exactly that.
    """
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return _start_authenticated_session(db, response, user.id, user.email)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """
    Ends the current authenticated session, if there is one.

    Deliberately idempotent rather than 401ing when there's no session
    to end: a logout button the frontend shows any time it believes
    the user is authenticated should always succeed from the caller's
    point of view, even in the (should-be-rare) case where the session
    had already expired or been cleared server-side by the time this
    request arrives -- the end state ("this browser is no longer
    treated as authenticated") is identical either way, which is all a
    logout call promises.

    Only ever touches the authenticated-session cookie/row -- never
    the guest session cookie, per this phase's brief ("Do not
    unnecessarily destroy unrelated guest-session infrastructure").
    The next request from this browser resolves to guest identity
    resolution exactly as it would for a browser that was never signed
    in.
    """
    token = request.cookies.get(settings.user_session_cookie_name)
    if token:
        user_session_service.delete_user_session(db, token)
    clear_user_session_cookie(response)

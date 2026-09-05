from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.requests import Request
from sqlalchemy.orm import Session

from app.api.deps import clear_user_session_cookie, set_user_session_cookie
from app.core.config import settings
from app.db.database import get_db
from app.schemas.auth import SigninRequest, SignupRequest
from app.schemas.identity import Identity, IdentityType
from app.services import auth_service, user_session_service

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
def signup(payload: SignupRequest, response: Response, db: Session = Depends(get_db)) -> Identity:
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
    """
    try:
        user = auth_service.create_user(db, payload.email, payload.password)
    except auth_service.EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

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

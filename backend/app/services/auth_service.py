"""
Account authentication (V3 Milestone 1 Phase 2): password hashing and
verification, and the User lookup/creation logic behind signup and
signin (app/api/v1/routes_auth.py). Same "thin route, real logic in a
directly-unit-testable service" convention as guest_session_service.py
and every other services/*.py file in this project.
"""

import bcrypt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User

# bcrypt silently truncates any input past 72 bytes -- two different
# passwords that only differ after that point would hash identically.
# Rather than pre-hashing with something else first to work around
# that (extra complexity for a limit no real password should ever
# hit), this project just rejects passwords long enough to reach it at
# the schema layer (see schemas/auth.py's SignupRequest.password) and
# treats this as a defensive backstop, since 72 *characters* (this
# constant) is already comfortably under 72 *bytes* even in the worst
# case (multi-byte UTF-8) -- no valid password the schema accepted
# should ever actually reach this truncation.
MAX_PASSWORD_BYTES_FOR_BCRYPT = 72


def normalize_email(email: str) -> str:
    """
    The one normalization applied to every email this app stores or
    looks up by: trimmed, lowercased. Applied identically on both the
    write path (signup) and the read path (signin, duplicate check) so
    "Alice@Example.com" and "alice@example.com" are always treated as
    the same account -- without needing a case-insensitive collation
    or index, which SQLite doesn't offer (see User's docstring in
    db/models.py).
    """
    return email.strip().lower()


def hash_password(password: str) -> str:
    """
    Hashes `password` with bcrypt, salted automatically and uniquely
    per call by `bcrypt.gensalt()` -- so two users who happen to pick
    the same password never end up with the same stored hash, and a
    stolen hash can't be attacked with a precomputed (rainbow-table)
    lookup. Returns a str (bcrypt's own hash format, ASCII) rather
    than raw bytes, matching `password_hash`'s String column and every
    other text column in this project.
    """
    password_bytes = password.encode("utf-8")[:MAX_PASSWORD_BYTES_FOR_BCRYPT]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Checks `password` against a stored bcrypt hash. Uses
    `bcrypt.checkpw`, which compares in constant time internally --
    this function never does its own `==` on hash output, which would
    reintroduce a timing side-channel bcrypt's own comparison already
    avoids.

    Returns False (never raises) for a malformed/corrupt stored hash,
    so a bad row can't turn "wrong password" into a 500 -- an invalid
    hash should behave like "this password doesn't match", not like a
    server error.
    """
    password_bytes = password.encode("utf-8")[:MAX_PASSWORD_BYTES_FOR_BCRYPT]
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return False


def get_user_by_email(db: Session, email: str) -> User | None:
    """
    Looks up a user by (normalized) email, or None if no account has
    it. Used both for the duplicate-account check in create_user and
    for signin's credential lookup.
    """
    return db.query(User).filter(User.email == normalize_email(email)).first()


class EmailAlreadyRegisteredError(Exception):
    """
    Raised by create_user when the email is already taken. A distinct
    exception type (rather than returning None, the way
    get_valid_guest_session signals "no session" for several different
    reasons on purpose) because here the route layer needs to tell
    this specific case apart from any other failure to answer with the
    right 409 -- see routes_auth.py's signup.
    """


def create_user(db: Session, email: str, password: str) -> User:
    """
    Creates and persists a new User, hashing `password` before it ever
    touches the database.

    Checks for an existing account with this email first (a normal,
    fast query) so the common case -- someone re-registering an
    address they already used -- gets a clean, immediate
    EmailAlreadyRegisteredError without ever reaching the database's
    own unique constraint. That constraint (`unique=True` on
    User.email, see db/models.py) is still the real backstop against
    two concurrent signups for the same address racing this check --
    caught here as an IntegrityError and converted to the same
    exception, so callers only ever need to handle one case, not two.
    """
    normalized_email = normalize_email(email)

    if get_user_by_email(db, normalized_email) is not None:
        raise EmailAlreadyRegisteredError(normalized_email)

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailAlreadyRegisteredError(normalized_email) from None
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """
    Verifies a login attempt, returning the User on success or None on
    any kind of failure -- no account with this email, or a wrong
    password. Deliberately not distinguishing those two cases in the
    return value (matching get_valid_guest_session's "the caller can't
    tell those apart, on purpose" reasoning): routes_auth.py's signin
    turns either outcome into the same generic "Invalid email or
    password" response, so a caller trying to enumerate which emails
    have accounts learns nothing from the response either way (see
    this phase's security requirement, "avoid unnecessarily revealing
    whether an account exists").
    """
    user = get_user_by_email(db, email)
    if user is None:
        # Still runs a bcrypt hash so this branch takes roughly the
        # same time as the "wrong password" branch below -- without
        # this, "no such account" would return measurably faster than
        # "wrong password", which is itself a (smaller, timing-based)
        # way to enumerate registered emails.
        hash_password(password)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user

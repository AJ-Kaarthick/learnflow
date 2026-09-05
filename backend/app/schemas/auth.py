import re
import string

from pydantic import BaseModel, Field, field_validator

# A deliberately loose "does this look like an email" check -- one
# `@`, something on each side, a `.` somewhere after it -- not a full
# RFC 5322 implementation. This project has no email-verification flow
# yet (see SignupRequest's docstring for why this schema still leaves
# room for one) and never sends mail to this address, so the only
# thing correctness here needs to guarantee is "a reasonable login
# identifier, not obvious garbage, and definitely not something like
# 'test@gmail' with no domain suffix at all" -- not "guaranteed
# deliverable". Pulling in `pydantic[email]` (the `email-validator`
# package) for a property this app doesn't yet rely on would be
# exactly the kind of unnecessary dependency this phase's brief says
# to avoid.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_EMAIL_FORMAT_ERROR = "Please enter a valid email address."

# Same sanity-cap reasoning as MAX_TITLE_LENGTH in schemas/conversation.py
# -- generous enough for any real email, small enough to reject garbage
# before it reaches the database.
MAX_EMAIL_LENGTH = 254

# Password policy (tightened after manual QA on the first Phase 2 pass
# surfaced that a signup like "11111111" -- 8 characters, nothing else
# -- was accepted). All five rules below are enforced together by
# `_validate_password_strength`, with one consolidated, friendly error
# message rather than pydantic's own per-constraint messages (see that
# function's docstring for why) -- this is also the same message shown
# proactively in the signup form before submission (see
# frontend/src/utils/authValidation.js's PASSWORD_REQUIREMENTS_MESSAGE,
# which intentionally mirrors this one word-for-word so the guidance
# text and the server-rejected message never say two different things).
MIN_PASSWORD_LENGTH = 8

# Matches auth_service.MAX_PASSWORD_BYTES_FOR_BCRYPT -- rejected here,
# at the API boundary, with a clear message, rather than silently
# truncated deep in the hashing call (see that constant's docstring
# for why truncation exists at all as a backstop).
MAX_PASSWORD_LENGTH = 72

_PASSWORD_REQUIREMENTS_MESSAGE = (
    "Password must be at least 8 characters and include an uppercase letter, "
    "a lowercase letter, a number, and a special character."
)

# Deliberately "any punctuation/symbol" (Python's own `string.punctuation`)
# rather than a hand-picked subset -- there's no security reason to
# reject a special character someone's password manager generated just
# because it isn't on a hand-picked list, and a hand-picked list is one
# more thing to keep in sync with the frontend's mirror of this rule
# (see authValidation.js) than reusing a language-standard set.
_SPECIAL_CHARACTERS = set(string.punctuation)


def _validate_email_format(value: str) -> str:
    email = value.strip()
    if not _EMAIL_PATTERN.match(email):
        raise ValueError(_EMAIL_FORMAT_ERROR)
    return email.lower()


def _validate_password_strength(value: str) -> str:
    """
    Enforces this phase's password policy: at least 8 characters, and
    at least one of each of uppercase, lowercase, digit, and special
    character. Deliberately implemented as one check that raises one
    consolidated message (`_PASSWORD_REQUIREMENTS_MESSAGE`) rather than
    several separate `Field`/validator constraints each with their own
    pydantic-generated message ("String should have at least 8
    characters", etc.) -- those default messages are accurate but not
    what a signup form should show (per this phase's UX requirement:
    "clear human-readable messages", not implementation-detail-shaped
    ones), and stacking multiple validators here would surface *all*
    of them at once as a list a signup form would have to stitch back
    together into one coherent sentence. A single check with one
    sentence is simpler for both this schema and its caller.

    Length is capped, not just floored: `MAX_PASSWORD_LENGTH` matches
    auth_service.MAX_PASSWORD_BYTES_FOR_BCRYPT, rejected here with a
    clear message rather than silently truncated deep in the hashing
    call.
    """
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be no more than {MAX_PASSWORD_LENGTH} characters.")

    meets_requirements = (
        len(value) >= MIN_PASSWORD_LENGTH
        and any(character.isupper() for character in value)
        and any(character.islower() for character in value)
        and any(character.isdigit() for character in value)
        and any(character in _SPECIAL_CHARACTERS for character in value)
    )
    if not meets_requirements:
        raise ValueError(_PASSWORD_REQUIREMENTS_MESSAGE)

    return value


class SignupRequest(BaseModel):
    """
    POST /auth/signup's request body. `email` is normalized
    (trimmed, lowercased) here at the schema boundary -- the same
    normalization auth_service.create_user applies again before
    storing/comparing it, so a request that somehow bypassed this
    schema (e.g. a future internal caller) still can't create a
    case-variant duplicate of an existing account.

    Note for future authentication work (not implemented in this
    phase): validating that this string is syntactically shaped like
    an email doesn't confirm the person submitting it actually owns
    that address. If/when email-ownership verification is added, it's
    a new `email_verified` column on `User` (db/models.py) plus a
    token/expiry table -- nothing about this schema's shape needs to
    change for that; a request here still just supplies "the email
    they're claiming".
    """

    email: str = Field(max_length=MAX_EMAIL_LENGTH)
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email_format(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class SigninRequest(BaseModel):
    """
    POST /auth/signin's request body. Email format is validated the
    same way as signup's -- an obviously-malformed email can never
    match a real account anyway, so rejecting it here is a cheap,
    honest 422 instead of a slower round trip to auth_service that
    would just come back "invalid credentials". Password has no
    strength/length validation here, deliberately unlike
    SignupRequest: a signin attempt is checked against whatever hash
    is actually stored, and rejecting a login attempt for "too short"
    or "missing a special character" before even checking it would be
    a way to (weakly) signal something about the account's password
    policy -- simplest to just let a policy-violating guess fail
    authentication like any other wrong password.
    """

    email: str = Field(max_length=MAX_EMAIL_LENGTH)
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email_format(value)

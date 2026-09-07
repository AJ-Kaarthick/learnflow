"""
Centralized guest usage limits (V3 Milestone 1 Phase 3).

"Guest access is an upgrade path, not a dead end" (this phase's
brief) -- guests can use LearnFlow for real, but only up to a limit
per usage dimension, after which they're pointed at signing up rather
than simply blocked. Enforcement lives here, server-side, and only
here: a route never compares a counter to a magic number itself, it
calls `enforce_limit` before doing the thing that counts, and
`record_usage` after that thing actually succeeds. This is what keeps
every limit's actual number in exactly one place (settings, see
core/config.py) rather than scattered across route files, and what
guarantees the frontend can never be the authority for enforcement --
it only ever finds out a limit was hit from this module's own 403,
same as any other request it didn't control.

Three usage dimensions, matching the three kinds of guest action this
phase's brief calls out as appropriate to the existing architecture:

- DOCUMENT_UPLOAD -- POST /documents/upload.
- AI_GENERATION -- summary, flashcards, quiz, and mind map generation,
  counted together as one dimension rather than four separate limits.
  These four are the same shape of action (spend one AI call to turn a
  document into study material) and, per the brief, a "minimal
  sensible implementation" shouldn't invent four independently-tuned
  limits for what is, from a guest's point of view, one kind of thing
  ("generate AI study material"). "Revision/practice usage" -- another
  dimension the brief names as possible -- isn't a separate limit for
  the same reason: LearnFlow has no server-side concept of a quiz
  attempt or a flashcard review to rate-limit (QuizQuestion's own
  docstring in db/models.py explains why grading is client-side, with
  nothing persisted per-attempt) -- the only server-side action
  "revision/practice" actually performs is generating the quiz/
  flashcard content in the first place, which AI_GENERATION already
  covers.
- CHAT_MESSAGE -- sending a message, whether through the persistent
  conversation endpoint or either stateless chat endpoint (all three
  are gated the same way, so a guest can't bypass the limit by calling
  a different chat route).

Each dimension is idempotent-generation-aware where it matters:
summary/flashcards/quiz/mindmap generation is cached (see e.g.
summary_service.generate_summary_for_document) -- re-requesting
already-generated content for the same document is a free cache hit,
not a new AI call, so the routes that call this module only ever do so
when they're about to generate something for the first time, never on
a cache hit. See each route's own call site for exactly where that
check happens.
"""

from enum import Enum

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import GuestSession
from app.schemas.identity import Identity, IdentityType


class GuestLimitType(str, Enum):
    DOCUMENT_UPLOAD = "document_upload"
    AI_GENERATION = "ai_generation"
    CHAT_MESSAGE = "chat_message"


def _limit_for(limit_type: GuestLimitType) -> int:
    """
    Reads the configured limit for `limit_type` fresh from `settings`
    every time, rather than snapshotting it into a module-level dict
    at import time -- settings are read from the environment once at
    process start (see core/config.py), so this is really about
    keeping this module's own lookup honest about where the number
    actually lives, and making a test that overrides `settings.*` at
    runtime (see tests/test_guest_limits.py) behave exactly as
    expected.
    """
    return {
        GuestLimitType.DOCUMENT_UPLOAD: settings.guest_max_documents,
        GuestLimitType.AI_GENERATION: settings.guest_max_ai_generations,
        GuestLimitType.CHAT_MESSAGE: settings.guest_max_chat_messages,
    }[limit_type]


_COUNTER_COLUMN = {
    GuestLimitType.DOCUMENT_UPLOAD: "document_upload_count",
    GuestLimitType.AI_GENERATION: "ai_generation_count",
    GuestLimitType.CHAT_MESSAGE: "chat_message_count",
}

_ACTION_DESCRIPTION = {
    GuestLimitType.DOCUMENT_UPLOAD: "upload documents",
    GuestLimitType.AI_GENERATION: "generate AI study material (summaries, flashcards, quizzes, and mind maps)",
    GuestLimitType.CHAT_MESSAGE: "send chat messages",
}


class GuestLimitExceededError(Exception):
    """
    Raised by `enforce_limit` when a guest has used up its allowance
    for a given dimension. Carries everything the route layer needs to
    build a predictable, machine-readable response (see
    `to_http_exception`) without the route itself knowing anything
    about how limits are configured or worded.
    """

    def __init__(self, limit_type: GuestLimitType, limit: int, used: int, message: str):
        self.limit_type = limit_type
        self.limit = limit
        self.used = used
        self.message = message
        super().__init__(message)


def _get_guest_session(db: Session, identity: Identity) -> GuestSession | None:
    """
    `identity.id` *is* a GuestSession.id for a guest identity (see
    GuestSession's docstring in db/models.py) -- this is always
    expected to resolve, since get_current_identity just created or
    touched this exact row earlier in the same request. The None case
    is a defensive fallback only (e.g. a row deleted between requests
    by some other process), treated as "zero usage so far" by both
    functions below rather than raising, so a freak missing row fails
    open to "let the guest through" rather than incorrectly blocking
    them.
    """
    return db.query(GuestSession).filter(GuestSession.id == identity.id).first()


def enforce_limit(db: Session, identity: Identity, limit_type: GuestLimitType) -> None:
    """
    Raises GuestLimitExceededError if `identity` (when a guest) has
    already reached its limit for `limit_type`. A no-op for an
    authenticated User -- guest limits apply only to guest identities,
    per this phase's brief ("Authenticated users must not accidentally
    inherit guest restrictions") -- so this is always safe to call
    unconditionally at the top of any route that also serves
    authenticated users.

    Call this BEFORE performing the action it gates (uploading,
    generating, sending), so a guest at the limit never pays the cost
    of an AI call or a file write for a request that's about to be
    rejected anyway.
    """
    if identity.type is not IdentityType.GUEST:
        return

    limit = _limit_for(limit_type)
    session = _get_guest_session(db, identity)
    used = getattr(session, _COUNTER_COLUMN[limit_type]) if session is not None else 0

    if used >= limit:
        raise GuestLimitExceededError(
            limit_type=limit_type,
            limit=limit,
            used=used,
            message=(
                f"Guests can {_ACTION_DESCRIPTION[limit_type]} up to {limit} times. "
                "Sign up for a free account to keep going -- it only takes a moment, "
                "and everything from this session comes with you."
            ),
        )


def record_usage(db: Session, identity: Identity, limit_type: GuestLimitType) -> None:
    """
    Increments `identity`'s counter for `limit_type`. A no-op for an
    authenticated User, matching enforce_limit.

    Call this AFTER the action it gates has actually succeeded (e.g.
    after the AI call returned, not before) -- so a failed attempt
    (a 502 from the AI provider, a validation error) never counts
    against a guest's limit; only real, completed usage does.
    """
    if identity.type is not IdentityType.GUEST:
        return

    session = _get_guest_session(db, identity)
    if session is None:
        return
    column = _COUNTER_COLUMN[limit_type]
    setattr(session, column, getattr(session, column) + 1)
    db.commit()


def to_http_exception(error: GuestLimitExceededError) -> HTTPException:
    """
    Converts a GuestLimitExceededError into the one predictable,
    machine-readable shape every guest-limit response uses, regardless
    of which route or which dimension hit it -- "predictable
    machine-readable error response" is this phase's own wording for
    what the backend owes the frontend here. `code` is what the
    frontend's error-handling (see frontend/src/api/errors.js) keys
    off of to show a "sign up to continue" affordance instead of a
    plain error message; `limit_type`/`limit`/`used` are included for
    a caller that wants to build its own copy instead of just
    displaying `message` verbatim.

    403, not 429: this isn't a request-rate limit that resets shortly
    on its own (there's no "try again in N seconds" that would ever
    help) -- it's a permission tied to being a guest at all, which
    only ever changes by creating an account, the same category of
    "you're not allowed to do this given who you are" as any other 403
    in this app.
    """
    return HTTPException(
        status_code=403,
        detail={
            "code": "guest_limit_reached",
            "limit_type": error.limit_type.value,
            "limit": error.limit,
            "used": error.used,
            "message": error.message,
        },
    )

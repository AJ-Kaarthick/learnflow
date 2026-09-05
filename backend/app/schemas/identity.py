from enum import Enum

from pydantic import BaseModel


class IdentityType(str, Enum):
    """
    The two kinds of identity LearnFlow can resolve a request to.

    V3 Milestone 1 Phase 1 only ever produced GUEST identities --
    account authentication is Phase 2, which is what now actually
    produces USER identities (see app/api/deps.py:get_current_identity
    and app/api/v1/routes_auth.py). USER existed even before that
    landed purely so the rest of the codebase (anything that branches
    on `identity.type`, or a future `Depends(require_authenticated_identity)`)
    was already written against the two-member shape it would actually
    have, instead of a guest-only shape that would need widening --
    and every callers' `match`/`if` over this enum later.
    """

    GUEST = "guest"
    USER = "user"


class Identity(BaseModel):
    """
    Answers "who is making this request?" -- the question Phase 1
    exists to establish (see app/api/deps.py:get_current_identity,
    the single place a request gets resolved to one of these).

    Deliberately minimal: just enough to say *which* guest or *which*
    user this is. It does NOT carry what that identity owns or is
    authorized to do -- that's "what data does this identity own, and
    what is it authorized to access?", which this phase's brief
    explicitly defers to Milestone 2 Phase 4 (Ownership + Authorization
    + Data Isolation). Routes/services that need to scope a query to
    "this identity's data" will take an Identity and look that up
    themselves once that system exists; nothing about this shape needs
    to change for them to do that.

    `id` is the identity's own id -- a GuestSession.id for a guest, or
    a User.id for an authenticated user (see db/models.py). Callers
    that only care about "is this the same identity as before" can
    compare `id` directly without caring which `type` it is.

    `email` (V3 Milestone 1 Phase 2) is the one piece of
    display-relevant information this phase adds: always `None` for a
    guest, always the account's email for an authenticated user. It's
    added here -- widening the existing shape -- rather than as a
    separate field on a new response type, per this phase's brief
    ("The existing identity endpoint should be extended or adapted as
    appropriate rather than creating unnecessary duplicate
    endpoints"): GET /identity/me stays the single place the frontend
    asks "who am I, and can I show their identity in the UI?", for
    both guest and authenticated requests, on refresh and otherwise.
    Deliberately not more than the email -- no display name, no
    account settings -- matching this whole model's "just enough to
    say which identity this is" scope; a richer profile is Milestone 2
    territory if it's ever needed at all.
    """

    type: IdentityType
    id: str
    email: str | None = None

    model_config = {"frozen": True}

    @property
    def is_guest(self) -> bool:
        return self.type is IdentityType.GUEST

    @property
    def is_user(self) -> bool:
        return self.type is IdentityType.USER

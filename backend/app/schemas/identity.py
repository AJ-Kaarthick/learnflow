from enum import Enum

from pydantic import BaseModel


class IdentityType(str, Enum):
    """
    The two kinds of identity LearnFlow can resolve a request to.

    V3 Milestone 1 Phase 1 only ever produces GUEST identities --
    account authentication is Phase 2. USER exists now purely so the
    rest of the codebase (anything that branches on `identity.type`,
    or a future `Depends(require_authenticated_identity)`) is written
    against the two-member shape it will actually have once Phase 2
    lands, instead of a guest-only shape that would need widening --
    and every callers' `match`/`if` over this enum later.
    """

    GUEST = "guest"
    USER = "user"


class Identity(BaseModel):
    """
    Answers "who is making this request?" -- the question this phase
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

    `id` is the identity's own id -- a GuestSession.id for a guest (see
    db/models.py), and will be a user account's id once Phase 2 exists.
    Callers that only care about "is this the same identity as before"
    can compare `id` directly without caring which `type` it is.
    """

    type: IdentityType
    id: str

    model_config = {"frozen": True}

    @property
    def is_guest(self) -> bool:
        return self.type is IdentityType.GUEST

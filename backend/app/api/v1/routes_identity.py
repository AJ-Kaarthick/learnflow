from fastapi import APIRouter, Depends

from app.api.deps import get_current_identity
from app.schemas.identity import Identity

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/me", response_model=Identity)
def get_me(identity: Identity = Depends(get_current_identity)) -> Identity:
    """
    Returns the identity the current request resolved to.

    Not part of any V3 Milestone 1 Phase 1 product requirement on its
    own -- this phase is foundation only, no UI is meant to change yet
    -- but it's the natural, minimal surface for the abstraction this
    phase exists to build: a place later phases' frontend work (e.g.
    "am I a guest? show the sign-up prompt") can call, and a place this
    phase's own tests can call to assert identity persistence/isolation
    end-to-end through a real request rather than only unit-testing
    guest_session_service.py directly.

    `identity` is declared as a normal parameter here (rather than only
    relying on `get_current_identity` running as a router-level
    dependency -- see app/main.py) so this route works correctly even
    in isolation; FastAPI's per-request dependency caching means this
    doesn't re-run the resolution logic or re-touch the session a
    second time when both apply in the same request.
    """
    return identity

"""
Ownership assignment and checks for guest/user-owned data (V3
Milestone 1 Phase 3: Guest Limits + Guest->Account Migration).

Before this phase, nothing in LearnFlow was owned by anyone -- every
Document and Conversation was visible to every request, guest or
authenticated (see Document.owner_type's docstring in db/models.py for
the full history). This module is the one place that answers "does
this identity own this row?", so every route that reads or writes a
Document/Conversation asks the same question the same way, rather than
each route file inventing its own comparison -- the one piece of this
phase's isolation requirement that's genuinely cross-cutting rather
than route-specific business logic (unlike each route file's own
"exists, is ready, ..." lookup, which stays per-file by this project's
existing convention -- see e.g. routes_summary.py's _get_ready_document
docstring).

Deliberately tiny: assigning an owner and checking one are both a
two-field comparison, nothing more. There's no ownership *model* here
(roles, sharing, transfer requests, ...) -- Milestone 2's territory if
it's ever needed -- just "whose is this, and is that the identity
asking".
"""

from sqlalchemy.orm import Query

from app.schemas.identity import Identity


def assign_owner(entity, identity: Identity) -> None:
    """
    Stamps `entity` (a Document or Conversation, at creation time) as
    belonging to `identity`. `owner_type` mirrors IdentityType's own
    values exactly ("guest" / "user") so there's only ever one
    vocabulary for "what kind of identity is this" across the whole
    app, not a second one that could drift out of sync with Identity's.
    """
    entity.owner_type = identity.type.value
    entity.owner_id = identity.id


def is_owned_by(entity, identity: Identity) -> bool:
    """
    True if `entity` belongs to `identity`, OR if `entity` has no
    owner at all.

    A null `owner_type` means this row predates Phase 3's ownership
    model, or was inserted directly against the database rather than
    through the API (this project's test fixtures do this routinely --
    see e.g. test_summary.py's _seed_ready_document_with_text). Such a
    row is treated as visible to everyone, exactly like every row
    already behaved before this phase existed -- not as belonging to
    no one and therefore unreachable. Every row created through the
    API from this phase on always has an owner (see assign_owner,
    called at creation time by every route that creates a Document or
    Conversation), so this fallback only ever applies to genuinely
    legacy/out-of-band data, never to anything a real guest or user
    created going forward -- the isolation guarantee this phase exists
    to add is not weakened by it.
    """
    if entity.owner_type is None:
        return True
    return entity.owner_type == identity.type.value and entity.owner_id == identity.id


def scope_to_owner(query: Query, model, identity: Identity) -> Query:
    """
    The list-query counterpart to is_owned_by, with one deliberate
    asymmetry: unlike is_owned_by, a null `owner_type` row is NOT
    included here.

    is_owned_by's "null owner = visible to everyone" rule exists so a
    direct link to a specific legacy/pre-Phase-3 row still opens (see
    that function's docstring) -- but a *list* is a different kind of
    surface. GET /documents and GET /conversations are each identity's
    personal library/sidebar; including every ownerless row in every
    single guest's and user's list -- even ones that happen to belong,
    in spirit, to some other identity's leftover legacy data -- would
    make every identity's "my documents" list show things that were
    never really theirs. Scoping the list strictly to rows this exact
    identity owns is both the more correct product behavior and the
    one that actually delivers this phase's isolation guarantee for
    the view guests and users look at most.
    """
    return query.filter(model.owner_type == identity.type.value, model.owner_id == identity.id)

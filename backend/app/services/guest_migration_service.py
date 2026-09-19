"""
Guest -> account data migration (V3 Milestone 1 Phase 3).

"Guest access is an upgrade path, not a dead end" -- when a guest
creates an account while their guest session is still active, the
data they already created as that guest should keep working exactly
as it did, just under the new account instead. This module is the one
place that performs that transfer; the only caller is
routes_auth.py's signup, which decides *whether* a migration should
happen (an active guest session must be present -- see that route's
own docstring) and hands this module the two ids involved once it has
decided.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Conversation, Document, RevisionSession
from app.schemas.identity import IdentityType
from app.services import guest_session_service


@dataclass(frozen=True)
class MigrationResult:
    documents_migrated: int
    conversations_migrated: int
    revision_sessions_migrated: int = 0


def migrate_guest_data_to_user(db: Session, guest_session_id: str, user_id: str) -> MigrationResult:
    """
    Transfers ownership of every Document and Conversation owned by
    `guest_session_id` to `user_id`, then revokes the guest session so
    it can never be resolved (and therefore never re-claimed or used
    to keep accumulating "guest" data) again.

    Only Document and Conversation are migrated -- the two entities
    this phase's brief calls out, and the only two tables that carry
    an owner column at all (see their docstrings in db/models.py).
    Everything else eligible for migration hangs off one of those two
    by a plain foreign key, with no owner of its own, and therefore
    needs no migration step of its own either:

    - Message and ConversationDocument are only ever reached via their
      parent conversation_id (see routes_conversations.py, which loads
      both by filtering on conversation_id, never independently) --
      once the parent Conversation's owner changes here, access to its
      messages and document associations changes with it, for free.
    - Summary, Flashcard, QuizQuestion, MindMap, and DocumentChunk are
      all reached only via their parent document_id (see e.g.
      routes_summary.py's _get_ready_document) -- migrating the parent
      Document is sufficient for the same reason.

    Atomic: both bulk UPDATEs and the guest-session revocation run
    against this same `db` Session and are committed together in one
    `db.commit()` at the end. If anything above raises before that
    commit runs, none of it is persisted -- the caller's own exception
    handling (routes_auth.py wraps this call in nothing extra; a
    failure here propagates as a 500, and FastAPI's request-scoped
    session is simply closed without a commit, per get_db's own
    docstring) leaves the database exactly as it was before migration
    was attempted, never with documents moved but conversations (or
    the guest session revocation) left behind.

    Guest usage counters (GuestSession.document_upload_count and
    friends) are deliberately NOT copied onto the new account --
    guest_limit_service's limits apply only to guest identities, so
    the new User starts completely unrestricted no matter how much its
    guest session had already used.

    Safe to call with a guest session that owns nothing: both bulk
    UPDATEs simply match zero rows, and the guest session is still
    revoked (there's no reason to leave an about-to-be-abandoned guest
    session claimable after its browser has just become an
    authenticated account) -- "if the guest has no persistent data,
    account creation should still work normally" per this phase's
    brief.
    """
    documents_migrated = (
        db.query(Document)
        .filter(Document.owner_type == IdentityType.GUEST.value, Document.owner_id == guest_session_id)
        .update({"owner_type": IdentityType.USER.value, "owner_id": user_id}, synchronize_session=False)
    )
    conversations_migrated = (
        db.query(Conversation)
        .filter(Conversation.owner_type == IdentityType.GUEST.value, Conversation.owner_id == guest_session_id)
        .update({"owner_type": IdentityType.USER.value, "owner_id": user_id}, synchronize_session=False)
    )
    revision_sessions_migrated = (
        db.query(RevisionSession)
        .filter(RevisionSession.owner_type == IdentityType.GUEST.value, RevisionSession.owner_id == guest_session_id)
        .update({"owner_type": IdentityType.USER.value, "owner_id": user_id}, synchronize_session=False)
    )

    guest_session_service.revoke_guest_session(db, guest_session_id)

    db.commit()

    return MigrationResult(
        documents_migrated=documents_migrated,
        conversations_migrated=conversations_migrated,
        revision_sessions_migrated=revision_sessions_migrated,
    )

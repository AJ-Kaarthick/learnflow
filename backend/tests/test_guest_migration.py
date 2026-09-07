"""
V3 Milestone 1 Phase 3: guest -> account data migration.

Covers app/services/guest_migration_service.py end-to-end through the
HTTP layer: signing up while a guest session is still active moves
that guest's documents and conversations (and, transitively, their
messages and document associations -- see that service's own
docstring for why those need no migration step of their own) onto the
new account, atomically, without duplication, and without leaving the
old guest session able to access (or re-claim) anything afterward.
Also covers the session-boundary rule this phase's brief is explicit
about: migration is only possible while the guest session is still
*active* -- an expired one is never resurrected, and its data is
simply gone, exactly like Phase 1's existing guest-expiration handling
already established for identity itself.

Deterministic expiration, same technique as
test_identity_session.py's own _backdate_last_seen: directly
backdating last_seen_at rather than sleeping or mocking the clock.
"""

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Conversation, Document, GuestSession, Message
from app.main import app

IDENTITY_URL = "/api/v1/identity/me"
SIGNUP_URL = "/api/v1/auth/signup"
UPLOAD_URL = "/api/v1/documents/upload"

VALID_PASSWORD = "Correct-Horse1!"


def _unique_email(label: str) -> str:
    return f"{label}.{datetime.now(timezone.utc).timestamp()}@example.com"


def _unique_filename(label: str) -> str:
    # Every test in this file shares one on-disk SQLite database for
    # the whole pytest session (see conftest.py) -- a fixed filename
    # like "notes.pdf" reused across tests would let one test's query
    # for "the document named notes.pdf" match a *different* test's
    # row, exactly the kind of collision every other file in this
    # suite avoids with its own unique id/tag per test.
    return f"{label}-{uuid.uuid4().hex[:8]}.pdf"


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload(client: TestClient, filename: str, text: str) -> str:
    response = client.post(
        UPLOAD_URL, files={"file": (filename, _make_test_pdf(text), "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _backdate_guest_session(session_id: str, minutes_ago: float) -> None:
    """Same technique as test_identity_session.py's own
    _backdate_last_seen -- deterministic, no sleeping or clock mocking."""
    db = SessionLocal()
    try:
        session = db.query(GuestSession).filter(GuestSession.id == session_id).first()
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        db.commit()
    finally:
        db.close()


def _sign_up(client: TestClient, label: str) -> dict:
    response = client.post(
        SIGNUP_URL, json={"email": _unique_email(label), "password": VALID_PASSWORD}
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Basic migration ------------------------------------------------------


def test_signup_with_no_prior_guest_activity_works_normally():
    """
    "If the guest has no persistent data, account creation should
    still work normally" -- the baseline every other test here builds
    on: migration is additive, never a precondition for signup.
    """
    client = TestClient(app)

    identity = _sign_up(client, "empty-guest")

    assert identity["type"] == "user"
    library = client.get("/api/v1/documents")
    assert library.status_code == 200
    assert library.json() == []


def test_guest_documents_migrate_to_the_new_account_on_signup():
    client = TestClient(app)
    first_name = _unique_filename("first")
    second_name = _unique_filename("second")
    _upload(client, first_name, "Guest's first document.")
    _upload(client, second_name, "Guest's second document.")

    _sign_up(client, "doc-migration")

    library = client.get("/api/v1/documents")
    assert library.status_code == 200
    filenames = {document["original_filename"] for document in library.json()}
    assert filenames == {first_name, second_name}


def test_migrated_documents_are_not_duplicated():
    client = TestClient(app)
    filename = _unique_filename("only")
    _upload(client, filename, "Guest's only document.")

    _sign_up(client, "no-duplication")

    db = SessionLocal()
    try:
        assert db.query(Document).filter(Document.original_filename == filename).count() == 1
    finally:
        db.close()


def test_guest_conversations_and_messages_migrate_to_the_new_account():
    client = TestClient(app)
    document_id = _upload(client, _unique_filename("convo"), "Content for a conversation.")
    create_response = client.post("/api/v1/conversations", json={"document_ids": [document_id]})
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    # A message is seeded directly (same convention test_conversations.py
    # itself uses) rather than through a real AI call -- this test is
    # about ownership migration, not chat orchestration.
    db = SessionLocal()
    try:
        db.add(
            Message(
                conversation_id=conversation_id,
                role="user",
                content="What is this document about?",
                position=0,
            )
        )
        db.commit()
    finally:
        db.close()

    _sign_up(client, "conversation-migration")

    detail = client.get(f"/api/v1/conversations/{conversation_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == conversation_id
    assert [document["id"] for document in body["documents"]] == [document_id]
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "What is this document about?"


def test_migrated_conversation_keeps_the_same_id_not_a_copy():
    """
    Migration transfers ownership in place (an UPDATE) rather than
    recreating the row -- the conversation's id a guest was already
    using stays valid and identical after signup, so nothing client-
    side needs to re-resolve "which conversation is this now".
    """
    client = TestClient(app)
    create_response = client.post("/api/v1/conversations", json={"document_ids": []})
    conversation_id = create_response.json()["id"]

    _sign_up(client, "same-id")

    detail = client.get(f"/api/v1/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == conversation_id

    db = SessionLocal()
    try:
        assert db.query(Conversation).filter(Conversation.id == conversation_id).count() == 1
    finally:
        db.close()


def test_guest_no_longer_independently_owns_migrated_data_after_signup():
    """
    The guest session itself is revoked as part of migration -- even
    if its cookie somehow survived signup, resolving identity from it
    again must not come back as the same guest with its old data still
    attached (see get_valid_guest_session's revoked_at filter).
    """
    client = TestClient(app)
    guest_identity = client.get(IDENTITY_URL).json()
    _upload(client, _unique_filename("revoke-check"), "Guest's document.")

    _sign_up(client, "guest-revoked")

    db = SessionLocal()
    try:
        guest_session = (
            db.query(GuestSession).filter(GuestSession.id == guest_identity["id"]).first()
        )
        assert guest_session is not None
        assert guest_session.revoked_at is not None
    finally:
        db.close()


def test_signup_does_not_migrate_a_different_browsers_guest_data():
    """
    Only the guest session presented by *this* signup request's own
    cookie is ever a migration source -- an unrelated guest elsewhere
    (a different TestClient, i.e. a different cookie jar/session, same
    isolation setup as test_identity_session.py) is completely
    unaffected by someone else creating an account.
    """
    unrelated_guest = TestClient(app)
    _upload(unrelated_guest, _unique_filename("unrelated"), "Someone else's document.")

    signup_client = TestClient(app)
    _sign_up(signup_client, "unrelated-signup")

    library = signup_client.get("/api/v1/documents")
    assert library.json() == []

    still_a_guest = unrelated_guest.get(IDENTITY_URL)
    assert still_a_guest.json()["type"] == "guest"
    still_has_document = unrelated_guest.get("/api/v1/documents")
    assert len(still_has_document.json()) == 1


# --- Expiration boundary ---------------------------------------------------


def test_expired_guest_session_data_is_not_migrated_on_signup():
    """
    "If the guest session has expired: do not resurrect expired guest
    data" -- an expired session is invisible to
    get_valid_guest_session, so signup proceeds as if there were no
    guest session at all, and the (now orphaned) document stays exactly
    where Phase 1's existing expiration behavior already leaves it:
    inaccessible.
    """
    client = TestClient(app)
    guest_identity = client.get(IDENTITY_URL).json()
    _upload(client, _unique_filename("expiring"), "About to expire.")
    _backdate_guest_session(
        guest_identity["id"], minutes_ago=settings.guest_session_inactivity_minutes + 1
    )

    identity_after_signup = _sign_up(client, "expired-guest")
    assert identity_after_signup["type"] == "user"

    library = client.get("/api/v1/documents")
    assert library.json() == []


def test_expired_guest_session_is_not_treated_as_migratable_by_anyone_else():
    """
    The same expired session can't be claimed by some *other*,
    unrelated account either -- there is no code path that looks a
    guest session up by anything other than "the cookie on this exact
    signup request", so an expired session's id being known (e.g. from
    a log, or guessed) grants no access to it.
    """
    guest_client = TestClient(app)
    guest_identity = guest_client.get(IDENTITY_URL).json()
    _upload(guest_client, _unique_filename("expiring-unclaimed"), "About to expire.")
    _backdate_guest_session(
        guest_identity["id"], minutes_ago=settings.guest_session_inactivity_minutes + 1
    )

    unrelated_signup_client = TestClient(app)
    _sign_up(unrelated_signup_client, "unrelated-account")

    library = unrelated_signup_client.get("/api/v1/documents")
    assert library.json() == []


def test_migration_atomicity_leaves_no_partial_transfer_on_failure(monkeypatch):
    """
    If anything goes wrong partway through a migration, nothing should
    have moved -- not just "mostly nothing". Simulated here by making
    the guest-session revocation step (which runs after both bulk
    ownership UPDATEs, see migrate_guest_data_to_user) explode, then
    asserting the Document transfer was rolled back too, exactly as if
    migration had never been attempted at all.
    """
    from app.services import guest_migration_service

    def _boom(*args, **kwargs):
        raise RuntimeError("Simulated failure partway through migration.")

    monkeypatch.setattr(guest_migration_service.guest_session_service, "revoke_guest_session", _boom)

    client = TestClient(app)
    guest_identity = client.get(IDENTITY_URL).json()
    filename = _unique_filename("atomic")
    _upload(client, filename, "Should not end up migrated.")

    # TestClient re-raises an unhandled exception from the route rather
    # than turning it into a response (Starlette's default
    # raise_server_exceptions=True) -- appropriate here, since this
    # test wants to know the *exception itself* propagated (proving
    # nothing caught and silently continued past it), not just that
    # some response eventually came back.
    with pytest.raises(RuntimeError):
        client.post(
            SIGNUP_URL,
            json={"email": _unique_email("atomic-failure"), "password": VALID_PASSWORD},
        )

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.original_filename == filename).first()
        assert document is not None
        # Still owned by the original guest session, not the (partially
        # created) user -- the failed transaction left ownership
        # exactly where it started.
        assert document.owner_type == "guest"
        assert document.owner_id == guest_identity["id"]

        guest_session = db.query(GuestSession).filter(GuestSession.id == guest_identity["id"]).first()
        assert guest_session.revoked_at is None
    finally:
        db.close()

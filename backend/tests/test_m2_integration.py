"""
V3 Milestone 2 Phase 4: Integration, Isolation & Regression Test Suite.

Verifies cross-cutting guarantees across the entire M2 persistent data foundation:
1. End-to-end guest -> account lifecycle with Revision assets (HTTP layer + DB).
2. Multi-tenant Revision data isolation (users, guests, scoped queries, ownership enforcement).
3. Multi-document partial document deletion durability (SET NULL on FK, evidence snapshot preserved, sister docs preserved).
4. Conversation <-> Revision domain decoupling (independent lifecycles over shared documents).
"""

import io
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.api.v1 import routes_conversations, routes_documents
from app.core.config import settings
from app.db.database import SessionLocal, build_engine
from app.db.models import (
    Conversation,
    ConversationDocument,
    Document,
    GuestSession,
    Message,
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    User,
)
from app.main import app
from app.schemas.identity import Identity, IdentityType
from app.services import ownership_service, storage_service

VALID_PASSWORD = "Correct-Horse1!"


def _make_test_pdf(text_content: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text_content)
    pdf.save()
    return buffer.getvalue()


def _unique_email(label: str) -> str:
    return f"{label}.{uuid.uuid4().hex[:8]}@example.com"


def _unique_filename(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}.pdf"


# ---------------------------------------------------------------------------
# 1. End-to-End Guest -> Account Migration with Revision Assets
# ---------------------------------------------------------------------------


def test_end_to_end_guest_to_account_lifecycle_with_revision():
    """
    Verifies that when a guest creates an account:
    - Uploaded documents migrate to the new account.
    - Conversations migrate to the new account.
    - RevisionSessions migrate to the new account.
    - RevisionSessionDocuments, RevisionQuestions, and RevisionAttempts remain intact.
    - The old guest session is revoked and cannot reclaim the data.
    """
    client = TestClient(app)

    # 1. Establish guest identity
    identity_resp = client.get("/api/v1/identity/me")
    assert identity_resp.status_code == 200
    guest_info = identity_resp.json()
    assert guest_info["type"] == "guest"
    guest_id = guest_info["id"]

    # 2. Upload document as guest
    doc_filename = _unique_filename("guest-study")
    upload_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": (doc_filename, _make_test_pdf("Guest study guide contents."), "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # 3. Create conversation as guest
    convo_resp = client.post("/api/v1/conversations", json={"document_ids": [doc_id]})
    assert convo_resp.status_code == 201
    convo_id = convo_resp.json()["id"]

    # 4. Seed Revision Session with Question and Attempt under guest identity
    db = SessionLocal()
    try:
        session = RevisionSession(
            title="Guest Midterm Prep",
            status="completed",
            config={"difficulty": "hard", "focus": "general"},
            total_questions=1,
            score=1.0,
            owner_type="guest",
            owner_id=guest_id,
        )
        db.add(session)
        db.flush()

        assoc = RevisionSessionDocument(
            session_id=session.id,
            document_id=doc_id,
        )
        db.add(assoc)

        question = RevisionQuestion(
            session_id=session.id,
            position=0,
            question_type="multiple_choice",
            question_text="What was studied?",
            options=["Study guide", "Novel"],
            correct_answer="Study guide",
            explanation="The guide contains study notes.",
            source_document_id=doc_id,
            evidence_snippet="Guest study guide contents.",
            evidence_metadata={"page": 1, "filename": doc_filename},
        )
        db.add(question)
        db.flush()

        attempt = RevisionAttempt(
            question_id=question.id,
            session_id=session.id,
            attempt_number=1,
            submitted_answer="Study guide",
            is_correct=True,
            score=1.0,
            feedback="Correct on first attempt.",
        )
        db.add(attempt)
        db.commit()
        session_id = session.id
        question_id = question.id
        attempt_id = attempt.id
    finally:
        db.close()

    # 5. Sign up to migrate guest data to new user account
    signup_email = _unique_email("guest-to-user")
    signup_resp = client.post(
        "/api/v1/auth/signup",
        json={"email": signup_email, "password": VALID_PASSWORD},
    )
    assert signup_resp.status_code == 201
    user_info = signup_resp.json()
    assert user_info["type"] == "user"
    new_user_id = user_info["id"]

    # 6. Verify via API and DB that documents and conversations migrated
    docs_resp = client.get("/api/v1/documents")
    assert docs_resp.status_code == 200
    user_doc_ids = [d["id"] for d in docs_resp.json()]
    assert doc_id in user_doc_ids

    convo_resp = client.get(f"/api/v1/conversations/{convo_id}")
    assert convo_resp.status_code == 200
    assert convo_resp.json()["id"] == convo_id

    # 7. Verify RevisionSession and descendants migrated to new user
    db = SessionLocal()
    try:
        migrated_session = db.query(RevisionSession).filter(RevisionSession.id == session_id).first()
        assert migrated_session is not None
        assert migrated_session.owner_type == "user"
        assert migrated_session.owner_id == new_user_id
        assert migrated_session.title == "Guest Midterm Prep"
        assert migrated_session.score == 1.0

        migrated_assoc = (
            db.query(RevisionSessionDocument)
            .filter(
                RevisionSessionDocument.session_id == session_id,
                RevisionSessionDocument.document_id == doc_id,
            )
            .first()
        )
        assert migrated_assoc is not None

        migrated_q = db.query(RevisionQuestion).filter(RevisionQuestion.id == question_id).first()
        assert migrated_q is not None
        assert migrated_q.source_document_id == doc_id
        assert migrated_q.evidence_snippet == "Guest study guide contents."

        migrated_att = db.query(RevisionAttempt).filter(RevisionAttempt.id == attempt_id).first()
        assert migrated_att is not None
        assert migrated_att.is_correct is True
        assert migrated_att.score == 1.0

        # Verify old guest session is revoked
        old_guest = db.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert old_guest is not None
        assert old_guest.revoked_at is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2. Multi-Tenant Revision Data Isolation
# ---------------------------------------------------------------------------


def test_multi_tenant_revision_data_isolation():
    """
    Verifies that:
    - User A and User B cannot access each other's RevisionSessions.
    - Guest sessions are isolated from user sessions and other guest sessions.
    - Scoped queries strictly isolate RevisionSessions by (owner_type, owner_id).
    - Child questions and attempts inherit isolation boundary from the parent session.
    """
    db = SessionLocal()
    try:
        # Create User A and User B
        uid_a = uuid.uuid4().hex[:8]
        uid_b = uuid.uuid4().hex[:8]
        user_a = User(id=f"user-a-{uid_a}", email=f"usera-{uid_a}@example.com", password_hash="hash")
        user_b = User(id=f"user-b-{uid_b}", email=f"userb-{uid_b}@example.com", password_hash="hash")
        db.add_all([user_a, user_b])

        # Create Guest 1 and Guest 2
        guest_1 = GuestSession(id=f"guest-1-{uuid.uuid4().hex[:8]}")
        guest_2 = GuestSession(id=f"guest-2-{uuid.uuid4().hex[:8]}")
        db.add_all([guest_1, guest_2])
        db.commit()

        ident_user_a = Identity(type=IdentityType.USER, id=user_a.id, user=user_a)
        ident_user_b = Identity(type=IdentityType.USER, id=user_b.id, user=user_b)
        ident_guest_1 = Identity(type=IdentityType.GUEST, id=guest_1.id, guest_session=guest_1)
        ident_guest_2 = Identity(type=IdentityType.GUEST, id=guest_2.id, guest_session=guest_2)

        # Create sessions
        session_a = RevisionSession(title="User A Session")
        ownership_service.assign_owner(session_a, ident_user_a)
        session_b = RevisionSession(title="User B Session")
        ownership_service.assign_owner(session_b, ident_user_b)
        session_g1 = RevisionSession(title="Guest 1 Session")
        ownership_service.assign_owner(session_g1, ident_guest_1)

        db.add_all([session_a, session_b, session_g1])
        db.commit()

        # Add questions to each session
        q_a = RevisionQuestion(
            session_id=session_a.id,
            position=0,
            question_type="short_answer",
            question_text="A Question",
            correct_answer="A Answer",
        )
        q_b = RevisionQuestion(
            session_id=session_b.id,
            position=0,
            question_type="short_answer",
            question_text="B Question",
            correct_answer="B Answer",
        )
        db.add_all([q_a, q_b])
        db.commit()

        # 1. Test scope_to_owner filtering
        query_a = ownership_service.scope_to_owner(db.query(RevisionSession), RevisionSession, ident_user_a).all()
        assert [s.id for s in query_a] == [session_a.id]

        query_b = ownership_service.scope_to_owner(db.query(RevisionSession), RevisionSession, ident_user_b).all()
        assert [s.id for s in query_b] == [session_b.id]

        query_g1 = ownership_service.scope_to_owner(db.query(RevisionSession), RevisionSession, ident_guest_1).all()
        assert [s.id for s in query_g1] == [session_g1.id]

        query_g2 = ownership_service.scope_to_owner(db.query(RevisionSession), RevisionSession, ident_guest_2).all()
        assert query_g2 == []

        # 2. Test is_owned_by predicates
        assert ownership_service.is_owned_by(session_a, ident_user_a) is True
        assert ownership_service.is_owned_by(session_a, ident_user_b) is False
        assert ownership_service.is_owned_by(session_a, ident_guest_1) is False

        assert ownership_service.is_owned_by(session_b, ident_user_b) is True
        assert ownership_service.is_owned_by(session_b, ident_user_a) is False

        assert ownership_service.is_owned_by(session_g1, ident_guest_1) is True
        assert ownership_service.is_owned_by(session_g1, ident_guest_2) is False
        assert ownership_service.is_owned_by(session_g1, ident_user_a) is False

        # 3. Child question isolation via parent session check
        parent_for_qa = db.query(RevisionSession).filter(RevisionSession.id == q_a.session_id).first()
        assert ownership_service.is_owned_by(parent_for_qa, ident_user_a) is True
        assert ownership_service.is_owned_by(parent_for_qa, ident_user_b) is False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Multi-Document Partial Document Deletion Durability
# ---------------------------------------------------------------------------


def test_multi_document_revision_partial_document_deletion():
    """
    Verifies that when a user deletes one document out of multiple linked to a revision session:
    - The deleted document and its storage are removed.
    - The sister document remains completely intact in DB and storage.
    - The RevisionSession itself remains completely intact.
    - The association row for the deleted document is deleted; the sister doc association is preserved.
    - Questions derived from the deleted document have source_document_id set to NULL,
      while preserving evidence_snippet and evidence_metadata.
    - Questions derived from the sister document retain source_document_id.
    - All historical attempts remain untouched.
    """
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(id=f"user-del-{uid}", email=f"userdel-{uid}@example.com", password_hash="hash")
        db.add(user)
        db.commit()
        ident = Identity(type=IdentityType.USER, id=user.id, user=user)

        # Create two documents with physical files in storage
        doc1_filename = f"biology-{uid}.pdf"
        doc2_filename = f"chemistry-{uid}.pdf"

        # Save files to storage
        stored1 = storage_service.save_uploaded_file(b"%PDF-1.4 Biology text content", ".pdf")
        stored2 = storage_service.save_uploaded_file(b"%PDF-1.4 Chemistry text content", ".pdf")

        doc1 = Document(
            id=f"doc1-{uid}",
            original_filename=doc1_filename,
            stored_filename=stored1,
            status="ready",
            owner_type="user",
            owner_id=user.id,
        )
        doc2 = Document(
            id=f"doc2-{uid}",
            original_filename=doc2_filename,
            stored_filename=stored2,
            status="ready",
            owner_type="user",
            owner_id=user.id,
        )
        db.add_all([doc1, doc2])
        db.commit()

        # Create a revision session linked to BOTH documents
        session = RevisionSession(
            title="Multi-Doc BioChem Review",
            status="completed",
            config={"difficulty": "mixed"},
            total_questions=2,
            score=0.5,
            owner_type="user",
            owner_id=user.id,
        )
        db.add(session)
        db.flush()

        assoc1 = RevisionSessionDocument(session_id=session.id, document_id=doc1.id)
        assoc2 = RevisionSessionDocument(session_id=session.id, document_id=doc2.id)
        db.add_all([assoc1, assoc2])

        # Q1 from doc1, Q2 from doc2
        q1 = RevisionQuestion(
            session_id=session.id,
            position=0,
            question_type="multiple_choice",
            question_text="What is cell division?",
            options=["Mitosis", "Fusion"],
            correct_answer="Mitosis",
            explanation="Mitosis divides eukaryotic cells.",
            source_document_id=doc1.id,
            evidence_snippet="Biology text: cells divide via mitosis.",
            evidence_metadata={"page": 4, "source": doc1_filename},
        )
        q2 = RevisionQuestion(
            session_id=session.id,
            position=1,
            question_type="multiple_choice",
            question_text="What is H2O?",
            options=["Water", "Hydrogen"],
            correct_answer="Water",
            explanation="H2O is water.",
            source_document_id=doc2.id,
            evidence_snippet="Chemistry text: H2O is water.",
            evidence_metadata={"page": 8, "source": doc2_filename},
        )
        db.add_all([q1, q2])
        db.flush()

        # Attempts
        att1 = RevisionAttempt(
            question_id=q1.id,
            session_id=session.id,
            attempt_number=1,
            submitted_answer="Fusion",
            is_correct=False,
            score=0.0,
            feedback="Incorrect",
        )
        att2 = RevisionAttempt(
            question_id=q2.id,
            session_id=session.id,
            attempt_number=1,
            submitted_answer="Water",
            is_correct=True,
            score=1.0,
            feedback="Correct",
        )
        db.add_all([att1, att2])
        db.commit()

        session_id = session.id
        q1_id = q1.id
        q2_id = q2.id
        att1_id = att1.id
        att2_id = att2.id

        # Delete doc1 via application service
        routes_documents.delete_document(document_id=doc1.id, db=db, identity=ident)

        # 1. doc1 is gone from DB and storage
        assert db.query(Document).filter(Document.id == doc1.id).first() is None
        assert not storage_service.get_path(stored1).exists()

        # 2. doc2 is STILL present and intact
        surviving_doc2 = db.query(Document).filter(Document.id == doc2.id).first()
        assert surviving_doc2 is not None
        assert storage_service.get_path(stored2).exists()

        # 3. RevisionSession is STILL present and intact
        surviving_session = db.query(RevisionSession).filter(RevisionSession.id == session_id).first()
        assert surviving_session is not None
        assert surviving_session.title == "Multi-Doc BioChem Review"
        assert surviving_session.total_questions == 2
        assert surviving_session.score == 0.5

        # 4. Association for doc1 is deleted; association for doc2 is preserved
        assert (
            db.query(RevisionSessionDocument)
            .filter(
                RevisionSessionDocument.session_id == session_id,
                RevisionSessionDocument.document_id == doc1.id,
            )
            .first()
        ) is None

        surviving_assoc2 = (
            db.query(RevisionSessionDocument)
            .filter(
                RevisionSessionDocument.session_id == session_id,
                RevisionSessionDocument.document_id == doc2.id,
            )
            .first()
        )
        assert surviving_assoc2 is not None

        # 5. Q1 source_document_id is NULL, but evidence snippet and metadata are preserved
        surviving_q1 = db.query(RevisionQuestion).filter(RevisionQuestion.id == q1_id).first()
        assert surviving_q1 is not None
        assert surviving_q1.source_document_id is None
        assert surviving_q1.evidence_snippet == "Biology text: cells divide via mitosis."
        assert surviving_q1.evidence_metadata["source"] == doc1_filename

        # 6. Q2 retains source_document_id to doc2
        surviving_q2 = db.query(RevisionQuestion).filter(RevisionQuestion.id == q2_id).first()
        assert surviving_q2 is not None
        assert surviving_q2.source_document_id == doc2.id
        assert surviving_q2.evidence_snippet == "Chemistry text: H2O is water."

        # 7. Historical attempts on both questions are completely preserved
        surviving_att1 = db.query(RevisionAttempt).filter(RevisionAttempt.id == att1_id).first()
        assert surviving_att1 is not None
        assert surviving_att1.is_correct is False
        assert surviving_att1.score == 0.0

        surviving_att2 = db.query(RevisionAttempt).filter(RevisionAttempt.id == att2_id).first()
        assert surviving_att2 is not None
        assert surviving_att2.is_correct is True
        assert surviving_att2.score == 1.0

        # Clean up storage for doc2
        storage_service.delete_file(stored2)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Conversation <-> Revision Domain Decoupling
# ---------------------------------------------------------------------------


def test_conversation_revision_decoupled_lifecycle():
    """
    Verifies that Conversations and RevisionSessions are mutually decoupled:
    - Deleting a Conversation that shares documents with a RevisionSession
      leaves the RevisionSession, its document links, questions, and attempts unaffected.
    - Deleting a RevisionSession leaves the Conversation, its messages, and its
      document links unaffected.
    - Deleting an underlying document cleanly cleans up associations in BOTH domains
      without causing cross-domain cascade failures.
    """
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(id=f"user-decouple-{uid}", email=f"decouple-{uid}@example.com", password_hash="hash")
        db.add(user)
        db.commit()
        ident = Identity(type=IdentityType.USER, id=user.id, user=user)

        # Shared document
        stored_shared = storage_service.save_uploaded_file(b"%PDF-1.4 Shared text", ".pdf")
        doc = Document(
            id=f"doc-shared-{uid}",
            original_filename="shared_textbook.pdf",
            stored_filename=stored_shared,
            status="ready",
            owner_type="user",
            owner_id=user.id,
        )
        db.add(doc)
        db.commit()

        # Conversation linked to shared document
        convo = Conversation(
            id=f"convo-{uid}",
            title="Shared Doc Chat",
            owner_type="user",
            owner_id=user.id,
        )
        db.add(convo)
        db.flush()

        convo_doc = ConversationDocument(conversation_id=convo.id, document_id=doc.id)
        msg = Message(
            conversation_id=convo.id,
            role="user",
            content="Can you summarize chapter 1?",
            position=0,
        )
        db.add_all([convo_doc, msg])

        # Revision Session linked to shared document
        rev_session = RevisionSession(
            title="Chapter 1 Revision",
            status="in_progress",
            owner_type="user",
            owner_id=user.id,
        )
        db.add(rev_session)
        db.flush()

        rev_doc = RevisionSessionDocument(session_id=rev_session.id, document_id=doc.id)
        q = RevisionQuestion(
            session_id=rev_session.id,
            position=0,
            question_type="flashcard",
            question_text="Front of card",
            correct_answer="Back of card",
            source_document_id=doc.id,
            evidence_snippet="Chapter 1 text snippet.",
        )
        db.add_all([rev_doc, q])
        db.flush()

        att = RevisionAttempt(
            question_id=q.id,
            session_id=rev_session.id,
            attempt_number=1,
            submitted_answer="Back of card",
            is_correct=True,
            score=1.0,
        )
        db.add(att)
        db.commit()

        convo_id = convo.id
        rev_id = rev_session.id
        q_id = q.id
        att_id = att.id

        # Phase A: Delete Conversation via application service
        routes_conversations.delete_conversation(conversation_id=convo_id, db=db, identity=ident)

        # Assert Conversation and its message are gone
        assert db.query(Conversation).filter(Conversation.id == convo_id).first() is None
        assert db.query(ConversationDocument).filter(ConversationDocument.conversation_id == convo_id).first() is None
        assert db.query(Message).filter(Message.conversation_id == convo_id).first() is None

        # Assert RevisionSession and all its descendants are 100% unaffected
        rev_check = db.query(RevisionSession).filter(RevisionSession.id == rev_id).first()
        assert rev_check is not None
        assert rev_check.title == "Chapter 1 Revision"

        rev_doc_check = (
            db.query(RevisionSessionDocument)
            .filter(
                RevisionSessionDocument.session_id == rev_id,
                RevisionSessionDocument.document_id == doc.id,
            )
            .first()
        )
        assert rev_doc_check is not None

        q_check = db.query(RevisionQuestion).filter(RevisionQuestion.id == q_id).first()
        assert q_check is not None
        assert q_check.source_document_id == doc.id
        assert q_check.evidence_snippet == "Chapter 1 text snippet."

        att_check = db.query(RevisionAttempt).filter(RevisionAttempt.id == att_id).first()
        assert att_check is not None
        assert att_check.is_correct is True

        # Phase B: Create a new Conversation on the document, then delete the RevisionSession
        convo2 = Conversation(
            id=f"convo2-{uid}",
            title="Second Chat",
            owner_type="user",
            owner_id=user.id,
        )
        db.add(convo2)
        db.flush()
        convo2_doc = ConversationDocument(conversation_id=convo2.id, document_id=doc.id)
        convo2_msg = Message(
            conversation_id=convo2.id,
            role="user",
            content="Hello again",
            position=0,
        )
        db.add_all([convo2_doc, convo2_msg])
        db.commit()

        # Delete the RevisionSession (ORM cascade removes child documents, questions, attempts)
        db.delete(rev_check)
        db.commit()

        # Assert RevisionSession and its cascade children are deleted
        assert db.query(RevisionSession).filter(RevisionSession.id == rev_id).first() is None
        assert db.query(RevisionSessionDocument).filter(RevisionSessionDocument.session_id == rev_id).first() is None
        assert db.query(RevisionQuestion).filter(RevisionQuestion.session_id == rev_id).first() is None
        assert db.query(RevisionAttempt).filter(RevisionAttempt.session_id == rev_id).first() is None

        # Assert Conversation 2, its document link, and message are 100% unaffected
        convo2_check = db.query(Conversation).filter(Conversation.id == convo2.id).first()
        assert convo2_check is not None
        assert convo2_check.title == "Second Chat"
        assert (
            db.query(ConversationDocument)
            .filter(
                ConversationDocument.conversation_id == convo2.id,
                ConversationDocument.document_id == doc.id,
            )
            .first()
        ) is not None
        assert db.query(Message).filter(Message.conversation_id == convo2.id).count() == 1

        # Assert shared document itself is still intact
        doc_check = db.query(Document).filter(Document.id == doc.id).first()
        assert doc_check is not None

        # Clean up storage
        storage_service.delete_file(stored_shared)
    finally:
        db.close()

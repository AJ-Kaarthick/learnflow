"""
V3 Milestone 2 Phase 3: Persistent Revision Data Model tests.

Tests the four new revision models:
- RevisionSession
- RevisionSessionDocument
- RevisionQuestion
- RevisionAttempt

Covers schema definitions, defaults, ownership isolation, multi-document associations,
question ordering, immutable learning evidence/provenance, attempt tracking,
cascade deletions, document deletion safety, guest-to-account migration,
and PostgreSQL compatibility.
"""

import os
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import Base, build_engine, get_db
from app.db.models import (
    Document,
    GuestSession,
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    User,
)
from app.main import app  # Ensures startup migrations run on test DB
from app.schemas.identity import Identity, IdentityType
from app.services import guest_migration_service, ownership_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Provides a transactional database session using the application engine."""
    engine = build_engine(settings.database_url)
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()


@pytest.fixture()
def user_identity(db_session: Session) -> Identity:
    uid = uuid.uuid4().hex[:8]
    user = User(id=f"test-user-rev-{uid}", email=f"revstudent-{uid}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    return Identity(type=IdentityType.USER, id=user.id, user=user)


@pytest.fixture()
def guest_identity(db_session: Session) -> Identity:
    uid = uuid.uuid4().hex[:8]
    guest = GuestSession(id=f"test-guest-rev-{uid}")
    db_session.add(guest)
    db_session.commit()
    return Identity(type=IdentityType.GUEST, id=guest.id, guest_session=guest)


@pytest.fixture()
def sample_documents(db_session: Session, user_identity: Identity) -> list[Document]:
    uid = uuid.uuid4().hex[:8]
    docs = [
        Document(
            id=f"doc-rev-1-{uid}",
            original_filename="biology.pdf",
            stored_filename=f"stored_biology_{uid}.pdf",
            status="ready",
            extracted_text="Cell division occurs through mitosis and meiosis.",
            owner_type=user_identity.type.value,
            owner_id=user_identity.id,
        ),
        Document(
            id=f"doc-rev-2-{uid}",
            original_filename="chemistry.pdf",
            stored_filename=f"stored_chemistry_{uid}.pdf",
            status="ready",
            extracted_text="Molecules are composed of bonded atoms.",
            owner_type=user_identity.type.value,
            owner_id=user_identity.id,
        ),
    ]
    db_session.add_all(docs)
    db_session.commit()
    return docs


# ---------------------------------------------------------------------------
# 1. Schema & Table Structure Tests
# ---------------------------------------------------------------------------

def test_revision_tables_and_columns_exist(db_session: Session):
    """Verifies that all four revision tables and their required columns exist."""
    inspector = inspect(db_session.bind)
    tables = set(inspector.get_table_names())

    assert "revision_sessions" in tables
    assert "revision_session_documents" in tables
    assert "revision_questions" in tables
    assert "revision_attempts" in tables

    # Check columns on revision_sessions
    session_cols = {c["name"] for c in inspector.get_columns("revision_sessions")}
    expected_session_cols = {
        "id", "title", "owner_type", "owner_id", "status", "config",
        "total_questions", "score", "created_at", "completed_at",
    }
    assert expected_session_cols.issubset(session_cols)

    # Check columns on revision_session_documents
    assoc_cols = {c["name"] for c in inspector.get_columns("revision_session_documents")}
    assert {"session_id", "document_id", "added_at"}.issubset(assoc_cols)

    # Check columns on revision_questions
    q_cols = {c["name"] for c in inspector.get_columns("revision_questions")}
    expected_q_cols = {
        "id", "session_id", "position", "question_type", "question_text",
        "options", "correct_answer", "explanation", "source_document_id",
        "source_chunk_id", "evidence_snippet", "evidence_metadata", "created_at",
    }
    assert expected_q_cols.issubset(q_cols)

    # Check columns on revision_attempts
    att_cols = {c["name"] for c in inspector.get_columns("revision_attempts")}
    expected_att_cols = {
        "id", "question_id", "session_id", "attempt_number", "submitted_answer",
        "is_correct", "score", "feedback", "evaluation_metadata", "created_at",
    }
    assert expected_att_cols.issubset(att_cols)


# ---------------------------------------------------------------------------
# 2. Revision Session Tests
# ---------------------------------------------------------------------------

def test_create_revision_session_defaults_and_custom(db_session: Session, user_identity: Identity):
    """Verifies creation of RevisionSession with default values and custom configuration."""
    session = RevisionSession(
        owner_type=user_identity.type.value,
        owner_id=user_identity.id,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert session.id is not None
    assert session.title == "Revision Session"
    assert session.status == "in_progress"
    assert session.total_questions == 0
    assert session.score is None
    assert session.completed_at is None
    assert isinstance(session.created_at, datetime)

    # Custom configuration
    custom_session = RevisionSession(
        title="Cell Biology Practice",
        status="completed",
        config={"difficulty": "hard", "question_count": 5},
        total_questions=5,
        score=4.5,
        completed_at=datetime.now(timezone.utc),
    )
    ownership_service.assign_owner(custom_session, user_identity)
    db_session.add(custom_session)
    db_session.commit()
    db_session.refresh(custom_session)

    assert custom_session.title == "Cell Biology Practice"
    assert custom_session.status == "completed"
    assert custom_session.config["difficulty"] == "hard"
    assert custom_session.score == 4.5
    assert custom_session.completed_at is not None


# ---------------------------------------------------------------------------
# 3. Ownership & Isolation Tests
# ---------------------------------------------------------------------------

def test_revision_session_ownership_user_and_guest(db_session: Session, user_identity: Identity, guest_identity: Identity):
    """Verifies that RevisionSession supports both user and guest identities."""
    user_session = RevisionSession(title="User Revision")
    ownership_service.assign_owner(user_session, user_identity)

    guest_session = RevisionSession(title="Guest Revision")
    ownership_service.assign_owner(guest_session, guest_identity)

    db_session.add_all([user_session, guest_session])
    db_session.commit()

    assert user_session.owner_type == "user"
    assert user_session.owner_id == user_identity.id
    assert ownership_service.is_owned_by(user_session, user_identity)
    assert not ownership_service.is_owned_by(user_session, guest_identity)

    assert guest_session.owner_type == "guest"
    assert guest_session.owner_id == guest_identity.id
    assert ownership_service.is_owned_by(guest_session, guest_identity)
    assert not ownership_service.is_owned_by(guest_session, user_identity)


def test_revision_session_no_normal_null_ownership(db_session: Session):
    """
    Verifies that normal V3 Revision sessions must always have an owner.
    Attempting to insert a RevisionSession without owner_type or owner_id fails.
    """
    session = RevisionSession(
        title="Unowned Session",
        owner_type=None,
        owner_id="some-id",
    )
    db_session.add(session)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    session2 = RevisionSession(
        title="Unowned Session 2",
        owner_type="user",
        owner_id=None,
    )
    db_session.add(session2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_revision_session_ownership_scoping(db_session: Session, user_identity: Identity, guest_identity: Identity):
    """Verifies that scope_to_owner isolates revision sessions between different identities."""
    s1 = RevisionSession(title="User Session 1")
    ownership_service.assign_owner(s1, user_identity)
    s2 = RevisionSession(title="User Session 2")
    ownership_service.assign_owner(s2, user_identity)
    s3 = RevisionSession(title="Guest Session 1")
    ownership_service.assign_owner(s3, guest_identity)

    db_session.add_all([s1, s2, s3])
    db_session.commit()

    user_query = ownership_service.scope_to_owner(db_session.query(RevisionSession), RevisionSession, user_identity)
    user_results = user_query.all()
    assert len(user_results) == 2
    assert {s.title for s in user_results} == {"User Session 1", "User Session 2"}

    guest_query = ownership_service.scope_to_owner(db_session.query(RevisionSession), RevisionSession, guest_identity)
    guest_results = guest_query.all()
    assert len(guest_results) == 1
    assert guest_results[0].title == "Guest Session 1"


# ---------------------------------------------------------------------------
# 4. Document Association Tests (Multi-Document)
# ---------------------------------------------------------------------------

def test_revision_session_multi_document_association(
    db_session: Session, user_identity: Identity, sample_documents: list[Document]
):
    """Verifies that a revision session can associate with multiple documents."""
    session = RevisionSession(title="Multi-Doc Session")
    ownership_service.assign_owner(session, user_identity)
    db_session.add(session)
    db_session.commit()

    doc1, doc2 = sample_documents
    assoc1 = RevisionSessionDocument(session_id=session.id, document_id=doc1.id)
    assoc2 = RevisionSessionDocument(session_id=session.id, document_id=doc2.id)
    db_session.add_all([assoc1, assoc2])
    db_session.commit()

    # Query associations
    assocs = (
        db_session.query(RevisionSessionDocument)
        .filter(RevisionSessionDocument.session_id == session.id)
        .all()
    )
    assert len(assocs) == 2
    associated_doc_ids = {a.document_id for a in assocs}
    assert associated_doc_ids == {doc1.id, doc2.id}

    # Verify ORM relationship traversal
    db_session.refresh(session)
    assert len(session.documents) == 2


def test_revision_session_duplicate_document_association_prevented(
    db_session: Session, user_identity: Identity, sample_documents: list[Document]
):
    """Verifies that composite primary key prevents duplicate document association."""
    session = RevisionSession(title="Unique Association Session")
    ownership_service.assign_owner(session, user_identity)
    db_session.add(session)
    db_session.commit()

    doc = sample_documents[0]
    assoc1 = RevisionSessionDocument(session_id=session.id, document_id=doc.id)
    db_session.add(assoc1)
    db_session.commit()

    # Attempt to associate the same document again in a separate session
    with Session(db_session.bind) as session2:
        assoc2 = RevisionSessionDocument(session_id=session.id, document_id=doc.id)
        session2.add(assoc2)
        with pytest.raises(IntegrityError):
            session2.commit()


# ---------------------------------------------------------------------------
# 5. Question & Provenance Tests
# ---------------------------------------------------------------------------

def test_revision_questions_belong_to_session_and_preserve_position(
    db_session: Session, user_identity: Identity, sample_documents: list[Document]
):
    """Verifies that questions belong to session, preserve position ordering, and store provenance."""
    session = RevisionSession(title="Questions Session", total_questions=2)
    ownership_service.assign_owner(session, user_identity)
    db_session.add(session)
    db_session.commit()

    doc = sample_documents[0]

    q1 = RevisionQuestion(
        session_id=session.id,
        position=0,
        question_type="multiple_choice",
        question_text="What process divides cells?",
        options=["Mitosis", "Diffusion", "Osmosis", "Respiration"],
        correct_answer="Mitosis",
        explanation="Mitosis produces two diploid daughter cells.",
        source_document_id=doc.id,
        source_chunk_id="chunk-123",
        evidence_snippet="Cell division occurs through mitosis and meiosis.",
        evidence_metadata={"document_name": doc.original_filename, "similarity": 0.94},
    )
    q2 = RevisionQuestion(
        session_id=session.id,
        position=1,
        question_type="multiple_choice",
        question_text="Which organelle produces ATP?",
        options=["Mitochondria", "Nucleus", "Ribosome", "Chloroplast"],
        correct_answer="Mitochondria",
        explanation="Mitochondria are the powerhouses of the cell.",
        source_document_id=doc.id,
        evidence_snippet="Mitochondria generate cellular energy.",
    )
    db_session.add_all([q1, q2])
    db_session.commit()

    # Query questions ordered by position
    questions = (
        db_session.query(RevisionQuestion)
        .filter(RevisionQuestion.session_id == session.id)
        .order_by(RevisionQuestion.position)
        .all()
    )
    assert len(questions) == 2
    assert questions[0].question_text == "What process divides cells?"
    assert questions[0].options == ["Mitosis", "Diffusion", "Osmosis", "Respiration"]
    assert questions[0].evidence_snippet == "Cell division occurs through mitosis and meiosis."
    assert questions[0].evidence_metadata["similarity"] == 0.94
    assert questions[1].position == 1


# ---------------------------------------------------------------------------
# 6. Attempt Tracking & Uniqueness Tests
# ---------------------------------------------------------------------------

def test_revision_attempts_multiple_and_correctness(db_session: Session, user_identity: Identity):
    """Verifies that attempts capture learner responses, correctness, score, and timestamps."""
    session = RevisionSession(title="Attempts Session")
    ownership_service.assign_owner(session, user_identity)
    db_session.add(session)
    db_session.commit()

    question = RevisionQuestion(
        session_id=session.id,
        position=0,
        question_type="multiple_choice",
        question_text="What is 2+2?",
        options=["3", "4", "5"],
        correct_answer="4",
    )
    db_session.add(question)
    db_session.commit()

    # Attempt 1: incorrect
    att1 = RevisionAttempt(
        question_id=question.id,
        session_id=session.id,
        attempt_number=1,
        submitted_answer="3",
        is_correct=False,
        score=0.0,
        feedback="Incorrect. 2+2 is 4.",
    )
    # Attempt 2: correct (retry)
    att2 = RevisionAttempt(
        question_id=question.id,
        session_id=session.id,
        attempt_number=2,
        submitted_answer="4",
        is_correct=True,
        score=1.0,
        feedback="Correct!",
    )
    db_session.add_all([att1, att2])
    db_session.commit()

    attempts = (
        db_session.query(RevisionAttempt)
        .filter(RevisionAttempt.question_id == question.id)
        .order_by(RevisionAttempt.attempt_number)
        .all()
    )
    assert len(attempts) == 2
    assert attempts[0].is_correct is False
    assert attempts[0].score == 0.0
    assert attempts[1].is_correct is True
    assert attempts[1].score == 1.0


def test_revision_attempts_unique_attempt_number_per_question(db_session: Session, user_identity: Identity):
    """Verifies that duplicate (question_id, attempt_number) violates the unique constraint."""
    session = RevisionSession(title="Constraint Session")
    ownership_service.assign_owner(session, user_identity)
    db_session.add(session)
    db_session.commit()

    question = RevisionQuestion(
        session_id=session.id,
        position=0,
        question_type="multiple_choice",
        question_text="True or False?",
        correct_answer="True",
    )
    db_session.add(question)
    db_session.commit()

    att1 = RevisionAttempt(
        question_id=question.id,
        session_id=session.id,
        attempt_number=1,
        submitted_answer="True",
        is_correct=True,
        score=1.0,
    )
    db_session.add(att1)
    db_session.commit()

    # Duplicate attempt_number for same question in a separate session
    with Session(db_session.bind) as session2:
        att2 = RevisionAttempt(
            question_id=question.id,
            session_id=session.id,
            attempt_number=1,
            submitted_answer="False",
            is_correct=False,
            score=0.0,
        )
        session2.add(att2)
        with pytest.raises(IntegrityError):
            session2.commit()


# ---------------------------------------------------------------------------
# 7. Cascades & Deletion Behavior Tests
# ---------------------------------------------------------------------------

def test_cascade_delete_session_removes_children(
    db_session: Session, user_identity: Identity, sample_documents: list[Document]
):
    """Verifies that deleting a RevisionSession removes its questions, attempts, and join rows."""
    session = RevisionSession(title="Session to Delete")
    ownership_service.assign_owner(session, user_identity)
    db_session.add(session)
    db_session.commit()

    doc = sample_documents[0]
    assoc = RevisionSessionDocument(session_id=session.id, document_id=doc.id)
    question = RevisionQuestion(
        session_id=session.id,
        position=0,
        question_type="multiple_choice",
        question_text="Q?",
        correct_answer="A",
    )
    db_session.add_all([assoc, question])
    db_session.commit()

    attempt = RevisionAttempt(
        question_id=question.id,
        session_id=session.id,
        attempt_number=1,
        submitted_answer="A",
        is_correct=True,
        score=1.0,
    )
    db_session.add(attempt)
    db_session.commit()

    q_id = question.id
    att_id = attempt.id
    s_id = session.id

    # Delete session
    db_session.delete(session)
    db_session.commit()

    # Verify children are gone
    assert db_session.query(RevisionSession).filter(RevisionSession.id == s_id).first() is None
    assert db_session.query(RevisionQuestion).filter(RevisionQuestion.id == q_id).first() is None
    assert db_session.query(RevisionAttempt).filter(RevisionAttempt.id == att_id).first() is None
    assert (
        db_session.query(RevisionSessionDocument)
        .filter(RevisionSessionDocument.session_id == s_id)
        .first()
    ) is None


def test_document_deletion_preserves_revision_session_and_evidence(
    db_session: Session, user_identity: Identity
):
    """
    Verifies the established V3 rule:
    Deleting a document removes it from future active use (deletes join row in
    RevisionSessionDocument and nullifies source_document_id), BUT leaves
    RevisionSession, RevisionQuestion, and RevisionAttempt rows intact with their
    evidence snapshots preserved.
    """
    from app.api.v1 import routes_documents

    # Create a document
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-del-{uid}",
        original_filename="notes.pdf",
        stored_filename=f"stored_notes_{uid}.pdf",
        status="ready",
        extracted_text="Historical study notes.",
        owner_type=user_identity.type.value,
        owner_id=user_identity.id,
    )
    db_session.add(doc)

    session = RevisionSession(title="Historical Session", total_questions=1, score=1.0)
    ownership_service.assign_owner(session, user_identity)
    db_session.add(session)
    db_session.commit()

    assoc = RevisionSessionDocument(session_id=session.id, document_id=doc.id)
    question = RevisionQuestion(
        session_id=session.id,
        position=0,
        question_type="multiple_choice",
        question_text="What was studied?",
        options=["Notes", "Books"],
        correct_answer="Notes",
        source_document_id=doc.id,
        evidence_snippet="Historical study notes snippet.",
        evidence_metadata={"document_name": "notes.pdf"},
    )
    db_session.add_all([assoc, question])
    db_session.commit()

    attempt = RevisionAttempt(
        question_id=question.id,
        session_id=session.id,
        attempt_number=1,
        submitted_answer="Notes",
        is_correct=True,
        score=1.0,
    )
    db_session.add(attempt)
    db_session.commit()

    s_id = session.id
    q_id = question.id
    att_id = attempt.id

    # Call delete_document through the application layer logic
    routes_documents.delete_document(document_id=doc.id, db=db_session, identity=user_identity)

    # Document is deleted
    assert db_session.query(Document).filter(Document.id == doc.id).first() is None

    # Association row is deleted (document is unlinked from session scope)
    assert (
        db_session.query(RevisionSessionDocument)
        .filter(RevisionSessionDocument.document_id == doc.id)
        .first()
    ) is None

    # Historical Session STILL EXISTS
    persisted_session = db_session.query(RevisionSession).filter(RevisionSession.id == s_id).first()
    assert persisted_session is not None
    assert persisted_session.title == "Historical Session"
    assert persisted_session.score == 1.0

    # Historical Question STILL EXISTS with evidence snippet
    persisted_question = db_session.query(RevisionQuestion).filter(RevisionQuestion.id == q_id).first()
    assert persisted_question is not None
    assert persisted_question.source_document_id is None  # FK cleanly nullified
    assert persisted_question.evidence_snippet == "Historical study notes snippet."
    assert persisted_question.evidence_metadata["document_name"] == "notes.pdf"

    # Historical Attempt STILL EXISTS
    persisted_attempt = db_session.query(RevisionAttempt).filter(RevisionAttempt.id == att_id).first()
    assert persisted_attempt is not None
    assert persisted_attempt.submitted_answer == "Notes"
    assert persisted_attempt.is_correct is True


# ---------------------------------------------------------------------------
# 8. Guest-to-Account Migration Tests
# ---------------------------------------------------------------------------

def test_guest_to_account_migration_transfers_revision_sessions(
    db_session: Session, guest_identity: Identity
):
    """
    Verifies that when a guest creates an account, all RevisionSession records
    owned by the guest session transfer ownership to the new user.
    """
    guest_session_id = guest_identity.id

    # Seed guest revision sessions
    s1 = RevisionSession(title="Guest Session 1")
    ownership_service.assign_owner(s1, guest_identity)
    s2 = RevisionSession(title="Guest Session 2")
    ownership_service.assign_owner(s2, guest_identity)

    db_session.add_all([s1, s2])
    db_session.commit()

    # Create new registered user
    uid = uuid.uuid4().hex[:8]
    target_user = User(id=f"user-post-guest-{uid}", email=f"converted-{uid}@example.com", password_hash="pass")
    db_session.add(target_user)
    db_session.commit()

    result = guest_migration_service.migrate_guest_data_to_user(
        db=db_session,
        guest_session_id=guest_session_id,
        user_id=target_user.id,
    )

    assert result.revision_sessions_migrated == 2

    # Verify both sessions now belong to user
    db_session.refresh(s1)
    db_session.refresh(s2)
    assert s1.owner_type == "user"
    assert s1.owner_id == target_user.id
    assert s2.owner_type == "user"
    assert s2.owner_id == target_user.id


# ---------------------------------------------------------------------------
# 9. Real PostgreSQL Integration Tests (Opt-in)
# ---------------------------------------------------------------------------

@pytest.mark.postgres
def test_real_postgres_revision_models():
    """
    Verifies Revision models, constraints, and cascades against a real PostgreSQL
    server when POSTGRES_TEST_DATABASE_URL is set.
    """
    postgres_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL not set; skipping live PostgreSQL test.")

    from alembic import command
    from app.db import migration_bootstrap

    # Ensure target PostgreSQL is migrated to Alembic head
    orig_url = settings.database_url
    settings.database_url = postgres_url
    try:
        command.upgrade(migration_bootstrap._alembic_config(), "head")
    finally:
        settings.database_url = orig_url

    pg_uid = uuid.uuid4().hex[:8]
    engine = build_engine(postgres_url)
    with Session(engine) as session:
        # Create user
        user = User(id=f"pg-rev-user-{pg_uid}", email=f"pguser-{pg_uid}@example.com", password_hash="hash")
        session.add(user)
        session.commit()

        # Create session
        rev_session = RevisionSession(
            id=f"pg-session-{pg_uid}",
            title="PostgreSQL Revision",
            owner_type="user",
            owner_id=user.id,
            total_questions=1,
            score=1.0,
        )
        session.add(rev_session)
        session.commit()

        # Create question
        question = RevisionQuestion(
            id=f"pg-q-{pg_uid}",
            session_id=rev_session.id,
            position=0,
            question_type="multiple_choice",
            question_text="PostgreSQL Question?",
            options=["A", "B"],
            correct_answer="A",
            evidence_snippet="PG evidence.",
        )
        session.add(question)
        session.commit()

        # Create attempt
        attempt = RevisionAttempt(
            id=f"pg-att-{pg_uid}",
            question_id=question.id,
            session_id=rev_session.id,
            attempt_number=1,
            submitted_answer="A",
            is_correct=True,
            score=1.0,
        )
        session.add(attempt)
        session.commit()

        # Verify uniqueness on PG
        dup_attempt = RevisionAttempt(
            question_id=question.id,
            session_id=rev_session.id,
            attempt_number=1,
            submitted_answer="B",
            is_correct=False,
            score=0.0,
        )
        session.add(dup_attempt)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # Verify cascade deletion on PG
        session.delete(rev_session)
        session.commit()

        assert session.query(RevisionSession).filter(RevisionSession.id == f"pg-session-{pg_uid}").first() is None
        assert session.query(RevisionQuestion).filter(RevisionQuestion.id == f"pg-q-{pg_uid}").first() is None
        assert session.query(RevisionAttempt).filter(RevisionAttempt.id == f"pg-att-{pg_uid}").first() is None

        # Clean up user
        session.delete(user)
        session.commit()

    engine.dispose()

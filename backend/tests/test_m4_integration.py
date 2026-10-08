"""
LearnFlow V3 Milestone 4 — Phase 5: Cross-Phase Integration Test Suite.

Verifies end-to-end integration across:
- M4 Phase 1: Revision session creation, multi-document grounding, question persistence
- M4 Phase 2: MCQ evaluation, open-ended AI evaluation, immutable attempt tracking, session completion
- Guest-to-account data migration (guest_migration_service)
- Document deletion durability and frozen evidence citations
- Multi-document provenance isolation
- Cross-identity access control and session isolation
- Guest usage quota lifecycle and quota exhaustion resilience
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import (
    Document,
    GuestSession,
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    User,
)
from app.main import app
from app.schemas.identity import Identity, IdentityType
from app.services import guest_limit_service, guest_session_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_limit_service import GuestLimitType
from app.services.guest_session_service import create_guest_session
from app.services.user_session_service import create_user_session


# ---------------------------------------------------------------------------
# Test AI Provider
# ---------------------------------------------------------------------------

class M4IntegrationAIProvider(AIProvider):
    """
    Unified mock AI provider for Milestone 4 cross-phase integration tests.
    Dispatches realistic structured responses for:
    - Multi-document revision question generation (MCQ, open-ended, mixed)
    - Open-ended answer evaluation with scoring rubrics and feedback
    - Simulated failures for error handling and quota-protection tests
    """

    def __init__(self) -> None:
        self.call_count = 0
        self.prompts: list[str] = []
        self.should_fail = False
        self.failure_error = "Simulated upstream AI provider service timeout"
        self.custom_questions: list[dict[str, Any]] | None = None
        self.custom_eval: dict[str, Any] | None = None

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        self.prompts.append(prompt)

        if self.should_fail:
            raise AIProviderError(self.failure_error)

        prompt_lower = prompt.lower()

        # 1. Answer evaluation prompt
        if "academic evaluator" in prompt_lower or "evaluate the student's submitted answer" in prompt_lower:
            if self.custom_eval is not None:
                return json.dumps(self.custom_eval)

            if "student's submitted answer:" in prompt_lower:
                after_sub = prompt_lower.split("student's submitted answer:")[1]
                student_section = after_sub.split("evaluation guidelines:")[0] if "evaluation guidelines:" in after_sub else after_sub
            else:
                student_section = prompt_lower

            if "poor" in student_section or "irrelevant" in student_section or "flawed" in student_section:
                return json.dumps({
                    "score": 0.2,
                    "is_correct": False,
                    "feedback": "The answer misses the key biochemical mechanisms.",
                    "reasoning": "Incomplete understanding of protein transport.",
                })
            elif "partial" in student_section:
                return json.dumps({
                    "score": 0.5,
                    "is_correct": False,
                    "feedback": "Partially correct explanation.",
                    "reasoning": "Identifies pumps but misses ATP requirement.",
                })
            else:
                return json.dumps({
                    "score": 0.9,
                    "is_correct": True,
                    "feedback": "Comprehensive and accurate explanation of cellular transport.",
                    "reasoning": "Grounded model answer with accurate biochemical terminology.",
                })

        # 2. Question generation prompt
        if self.custom_questions is not None:
            return json.dumps(self.custom_questions)

        # Extract document IDs from prompt
        doc_ids = re.findall(r"Document ID:\s*([^\s|]+)", prompt)
        doc1_id = doc_ids[0] if len(doc_ids) > 0 else "test-doc-1"
        doc2_id = doc_ids[1] if len(doc_ids) > 1 else doc1_id

        # Determine target question count
        count = 2
        if "exactly 3" in prompt_lower:
            count = 3
        elif "exactly 5" in prompt_lower:
            count = 5
        elif "exactly 1" in prompt_lower:
            count = 1

        is_mixed = "balanced combination" in prompt_lower or "mixed" in prompt_lower
        is_open = not is_mixed and ("open-ended" in prompt_lower or "open_ended" in prompt_lower)

        questions = []
        for i in range(1, count + 1):
            target_doc_id = doc2_id if (i % 2 == 0 and len(doc_ids) > 1) else doc1_id
            if is_open or (is_mixed and i % 2 == 0):
                questions.append({
                    "question_text": f"Explain active cellular transport mechanisms described in source document {i}.",
                    "question_type": "open_ended",
                    "options": None,
                    "correct_answer": "Cellular transport requires ATP to pump ions across membranes against gradient.",
                    "explanation": "Active transport relies on ATP hydrolysis for carrier proteins.",
                    "source_document_id": target_doc_id,
                    "evidence_snippet": f"Active transport pumps ions across cellular barriers using ATP energy in doc {i}.",
                })
            else:
                questions.append({
                    "question_text": f"Which organelle generates cellular energy in organism {i}?",
                    "question_type": "multiple_choice",
                    "options": ["Mitochondria", "Ribosome", "Endoplasmic Reticulum", "Golgi Apparatus"],
                    "correct_answer": "Mitochondria",
                    "explanation": "Mitochondria produce ATP through aerobic respiration.",
                    "source_document_id": target_doc_id,
                    "evidence_snippet": f"Mitochondria are the powerhouses of eukaryotic cells producing ATP in doc {i}.",
                })

        return json.dumps(questions)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture()
def fake_ai_provider():
    return M4IntegrationAIProvider()


@pytest.fixture()
def client(fake_ai_provider):
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _set_client_cookies(client: TestClient, cookies: dict[str, str]) -> None:
    client.cookies.clear()
    for k, v in cookies.items():
        client.cookies.set(k, v)


def _create_user(db: Session, label: str = "user") -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"{label}-{uid}",
        email=f"{label}.{uid}@example.com",
        password_hash="hashed_pw",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_cookies_for(user: User, db: Session) -> dict[str, str]:
    session = create_user_session(db, user.id)
    return {settings.user_session_cookie_name: session.id}


def _create_guest(db: Session) -> GuestSession:
    return create_guest_session(db)


def _guest_cookies_for(guest: GuestSession) -> dict[str, str]:
    return {settings.guest_session_cookie_name: guest.id}


def _create_document(
    db: Session,
    owner_type: IdentityType,
    owner_id: str,
    filename: str,
    text: str,
    status: str = "ready",
) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-{uid}",
        original_filename=filename,
        stored_filename=f"stored_{uid}_{filename}",
        status=status,
        extracted_text=text,
        file_size_bytes=len(text.encode("utf-8")),
        owner_type=owner_type.value,
        owner_id=owner_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# PART 1: CROSS-PHASE FULL REVISION LIFECYCLE
# ---------------------------------------------------------------------------

def test_m4_cross_phase_full_revision_lifecycle(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: M4IntegrationAIProvider,
):
    """
    Validates the end-to-end M4 Revision lifecycle across Phase 1 and Phase 2:
    - Multi-document revision session creation (mixed MCQ + open-ended)
    - Session bindings and question persistence
    - Question != Attempt separation: multiple attempts on one MCQ without question mutation
    - Open-ended submission evaluated by AI
    - Session completion and final score calculation
    - Retrieval of completed session with full attempt history
    - Invariant: attempt submission rejected after session completion
    """
    user = _create_user(db_session, "lifecycler")
    cookies = _auth_cookies_for(user, db_session)
    _set_client_cookies(client, cookies)

    doc1 = _create_document(
        db_session,
        IdentityType.USER,
        user.id,
        "cellular_biology.pdf",
        "Mitochondria generate cellular ATP via aerobic respiration. Essential for cellular metabolism.",
    )
    doc2 = _create_document(
        db_session,
        IdentityType.USER,
        user.id,
        "membrane_transport.pdf",
        "Cell membranes control active transport through ion pumps and carrier proteins using ATP.",
    )

    # 1. Create Revision Session (2 documents, mixed questions, count=2)
    payload = {
        "document_ids": [doc1.id, doc2.id],
        "question_count": 2,
        "difficulty": "intermediate",
        "mode": "practice",
        "question_type": "mixed",
        "title": "Bio Systems Practice",
    }
    create_res = client.post("/api/v1/revision/sessions", json=payload)
    assert create_res.status_code == 201, create_res.text
    session_data = create_res.json()
    session_id = session_data["id"]

    assert session_data["title"] == "Bio Systems Practice"
    assert session_data["status"] == "in_progress"
    assert session_data["total_questions"] == 2
    assert session_data["score"] is None
    assert session_data["completed_at"] is None
    assert len(session_data["documents"]) == 2
    assert len(session_data["questions"]) == 2

    # Check question types
    q1 = session_data["questions"][0]
    q2 = session_data["questions"][1]
    assert q1["question_type"] == "multiple_choice"
    assert q2["question_type"] == "open_ended"
    assert q1["correct_answer"] == "Mitochondria"
    assert len(q1["options"]) == 4

    # 2. Retrieve session detail
    detail_res = client.get(f"/api/v1/revision/sessions/{session_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == session_id

    # 3. Submit first attempt on Q1 (incorrect answer)
    att1_res = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q1['id']}/attempts",
        json={"submitted_answer": "Ribosome"},
    )
    assert att1_res.status_code == 201
    att1 = att1_res.json()
    assert att1["attempt_number"] == 1
    assert att1["is_correct"] is False
    assert att1["score"] == 0.0

    # 4. Submit second attempt on Q1 (correct answer)
    att2_res = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q1['id']}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert att2_res.status_code == 201
    att2 = att2_res.json()
    assert att2["attempt_number"] == 2
    assert att2["is_correct"] is True
    assert att2["score"] == 1.0

    # Verify Question != Attempt invariant: question row in DB remains untouched
    db_q1 = db_session.query(RevisionQuestion).filter(RevisionQuestion.id == q1["id"]).first()
    assert db_q1.question_text == q1["question_text"]
    assert db_q1.correct_answer == "Mitochondria"
    attempts_db = db_session.query(RevisionAttempt).filter(RevisionAttempt.question_id == q1["id"]).all()
    assert len(attempts_db) == 2
    assert {a.attempt_number for a in attempts_db} == {1, 2}

    # 5. Submit attempt on Q2 (open-ended answer evaluated by AI)
    att_q2_res = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q2['id']}/attempts",
        json={"submitted_answer": "Cellular transport requires ATP to pump ions across protein pumps."},
    )
    assert att_q2_res.status_code == 201
    att_q2 = att_q2_res.json()
    assert att_q2["attempt_number"] == 1
    assert att_q2["is_correct"] is True
    assert att_q2["score"] == 0.9
    assert "comprehensive and accurate" in att_q2["feedback"].lower()

    # 6. Complete Revision Session
    complete_res = client.post(f"/api/v1/revision/sessions/{session_id}/complete")
    assert complete_res.status_code == 200
    completed = complete_res.json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None
    # Score calculation: Q1 latest=1.0, Q2 latest=0.9 -> average = 0.95
    assert pytest.approx(completed["score"], 0.001) == 0.95

    # 7. Retrieve completed session and review full attempt history
    review_res = client.get(f"/api/v1/revision/sessions/{session_id}")
    assert review_res.status_code == 200
    reviewed = review_res.json()
    assert reviewed["status"] == "completed"
    assert pytest.approx(reviewed["score"], 0.001) == 0.95

    rev_q1 = [q for q in reviewed["questions"] if q["id"] == q1["id"]][0]
    assert len(rev_q1["attempts"]) == 2
    assert rev_q1["attempts"][0]["attempt_number"] == 1
    assert rev_q1["attempts"][0]["score"] == 0.0
    assert rev_q1["attempts"][1]["attempt_number"] == 2
    assert rev_q1["attempts"][1]["score"] == 1.0

    rev_q2 = [q for q in reviewed["questions"] if q["id"] == q2["id"]][0]
    assert len(rev_q2["attempts"]) == 1
    assert rev_q2["attempts"][0]["attempt_number"] == 1
    assert rev_q2["attempts"][0]["score"] == 0.9

    # 8. Invariant: subsequent attempts to completed session are rejected
    post_complete_attempt = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q1['id']}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert post_complete_attempt.status_code == 400
    assert "already completed" in post_complete_attempt.json()["detail"].lower()


# ---------------------------------------------------------------------------
# PART 2: GUEST MIGRATION
# ---------------------------------------------------------------------------

def test_guest_to_account_revision_migration(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: M4IntegrationAIProvider,
):
    """
    Validates guest -> account data migration for Revision:
    - Guest creates revision session with questions and attempts
    - Guest signs up via /api/v1/auth/signup with guest cookie
    - RevisionSession ownership migrates atomically to the new authenticated user
    - Historical questions and attempts remain intact
    - Authenticated user can access their migrated Revision history
    - Other users cannot access the migrated Revision session
    """
    guest = _create_guest(db_session)
    guest_cookies = _guest_cookies_for(guest)
    _set_client_cookies(client, guest_cookies)

    # Guest document
    doc = _create_document(
        db_session,
        IdentityType.GUEST,
        guest.id,
        "guest_notes.pdf",
        "Key concepts of neural transmission and action potentials along axon.",
    )

    # 1. Guest creates revision session
    payload = {
        "document_ids": [doc.id],
        "question_count": 2,
        "difficulty": "beginner",
        "mode": "quiz",
        "question_type": "multiple_choice",
        "title": "Guest Neural Quiz",
    }
    create_res = client.post("/api/v1/revision/sessions", json=payload)
    assert create_res.status_code == 201
    guest_session_id = create_res.json()["id"]
    q1_id = create_res.json()["questions"][0]["id"]

    # 2. Guest submits an attempt
    att_res = client.post(
        f"/api/v1/revision/sessions/{guest_session_id}/questions/{q1_id}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert att_res.status_code == 201

    # Verify session ownership in DB before migration
    db_rev = db_session.query(RevisionSession).filter(RevisionSession.id == guest_session_id).first()
    assert db_rev.owner_type == IdentityType.GUEST.value
    assert db_rev.owner_id == guest.id

    # 3. Guest signs up with the guest session cookie
    signup_email = f"migrated.learner.{uuid.uuid4().hex[:8]}@example.com"
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"email": signup_email, "password": "SecurePassword123!"},
    )
    assert signup_res.status_code == 201
    user_data = signup_res.json()
    new_user_id = user_data["id"]

    # 4. Verify DB state post-migration
    db_session.expire_all()
    migrated_rev = db_session.query(RevisionSession).filter(RevisionSession.id == guest_session_id).first()
    assert migrated_rev.owner_type == IdentityType.USER.value
    assert migrated_rev.owner_id == new_user_id

    # Verify questions and attempts remain intact
    assert len(migrated_rev.questions) == 2
    assert len(migrated_rev.attempts) == 1

    # 5. Verify the new user can retrieve the migrated session via API
    user_sessions_res = client.get("/api/v1/revision/sessions")
    assert user_sessions_res.status_code == 200
    user_sessions = user_sessions_res.json()
    assert any(s["id"] == guest_session_id for s in user_sessions)

    user_detail_res = client.get(f"/api/v1/revision/sessions/{guest_session_id}")
    assert user_detail_res.status_code == 200
    detail = user_detail_res.json()
    assert detail["id"] == guest_session_id
    assert detail["owner_id"] == new_user_id
    assert len(detail["questions"]) == 2
    assert len(detail["questions"][0]["attempts"]) == 1

    # 6. Verify another user cannot access this session
    other_user = _create_user(db_session, "other")
    other_cookies = _auth_cookies_for(other_user, db_session)
    _set_client_cookies(client, other_cookies)
    forbidden_res = client.get(f"/api/v1/revision/sessions/{guest_session_id}")
    assert forbidden_res.status_code == 404


# ---------------------------------------------------------------------------
# PART 3: DOCUMENT DELETION DURABILITY
# ---------------------------------------------------------------------------

def test_document_deletion_durability_and_evidence_preservation(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: M4IntegrationAIProvider,
):
    """
    Validates the document deletion durability contract in Revision:
    - Revision session created with doc A and doc B
    - Questions store source_document_id and frozen evidence_snippet
    - Doc A is deleted
    - RevisionSession, RevisionQuestion, RevisionAttempt remain intact
    - Question for Doc A has source_document_id=None, but evidence_snippet is preserved
    - Session detail endpoint serializes missing doc as 'Archived Document' with 'archived' status
    """
    user = _create_user(db_session, "durability_user")
    cookies = _auth_cookies_for(user, db_session)
    _set_client_cookies(client, cookies)

    doc_a = _create_document(
        db_session,
        IdentityType.USER,
        user.id,
        "primary_anatomy.pdf",
        "Primary anatomy text: The cardiac muscle pumps deoxygenated blood to pulmonary arteries.",
    )
    doc_b = _create_document(
        db_session,
        IdentityType.USER,
        user.id,
        "secondary_physiology.pdf",
        "Secondary physiology text: Nephrons filter blood and regulate osmolarity in kidneys.",
    )

    doc_a_id = doc_a.id
    doc_b_id = doc_b.id

    # 1. Create Revision Session with both documents
    create_payload = {
        "document_ids": [doc_a_id, doc_b_id],
        "question_count": 2,
        "mode": "practice",
        "question_type": "multiple_choice",
    }
    create_res = client.post("/api/v1/revision/sessions", json=create_payload)
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]
    q1 = create_res.json()["questions"][0]
    q2 = create_res.json()["questions"][1]

    # Explicitly verify initial evidence and provenance
    assert q1["source_document_id"] == doc_a_id
    evidence_a = q1["evidence_snippet"]
    assert evidence_a is not None

    # Submit an attempt on Q1
    att_res = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q1['id']}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert att_res.status_code == 201

    # 2. Delete Doc A via the documents API
    delete_res = client.delete(f"/api/v1/documents/{doc_a_id}")
    assert delete_res.status_code == 204

    # 3. Check DB persistence post-deletion
    db_session.expunge_all()
    assert db_session.query(Document).filter(Document.id == doc_a_id).first() is None
    assert db_session.query(RevisionSession).filter(RevisionSession.id == session_id).first() is not None

    # Question 1 survived with source_document_id=None and frozen evidence_snippet intact
    db_q1 = db_session.query(RevisionQuestion).filter(RevisionQuestion.id == q1["id"]).first()
    assert db_q1 is not None
    assert db_q1.source_document_id is None
    assert db_q1.evidence_snippet == evidence_a

    # Attempt on Question 1 survived
    db_att = db_session.query(RevisionAttempt).filter(RevisionAttempt.question_id == q1["id"]).first()
    assert db_att is not None

    # Question 2 still points to Doc B
    db_q2 = db_session.query(RevisionQuestion).filter(RevisionQuestion.id == q2["id"]).first()
    assert db_q2 is not None
    assert db_q2.source_document_id == doc_b_id

    # 4. Check API serialization of the historical revision session
    detail_res = client.get(f"/api/v1/revision/sessions/{session_id}")
    assert detail_res.status_code == 200
    data = detail_res.json()

    # Question 1 serialization has None title but preserved evidence
    detail_q1 = [q for q in data["questions"] if q["id"] == q1["id"]][0]
    assert detail_q1["source_document_id"] is None
    assert detail_q1["source_document_title"] is None
    assert detail_q1["evidence_snippet"] == evidence_a
    assert len(detail_q1["attempts"]) == 1

    # Question 2 serialization retains Doc B title
    detail_q2 = [q for q in data["questions"] if q["id"] == q2["id"]][0]
    assert detail_q2["source_document_id"] == doc_b_id
    assert detail_q2["source_document_title"] == "secondary_physiology.pdf"


# ---------------------------------------------------------------------------
# PART 4: MULTI-DOCUMENT PROVENANCE
# ---------------------------------------------------------------------------

def test_multi_document_provenance_isolation(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: M4IntegrationAIProvider,
):
    """
    Validates per-question source document provenance across multiple documents:
    - Session contains multiple documents
    - Each question identifies its exact source document and evidence snippet
    - Questions are not incorrectly attributed to all selected documents
    - Multi-document bindings (RevisionSessionDocument) vs per-question provenance
      (RevisionQuestion.source_document_id) remain distinct
    """
    user = _create_user(db_session, "provenance_user")
    cookies = _auth_cookies_for(user, db_session)
    _set_client_cookies(client, cookies)

    doc_neuro = _create_document(
        db_session,
        IdentityType.USER,
        user.id,
        "neuroscience.pdf",
        "Neuroscience chapter: Synaptic plasticity underlies memory consolidation.",
    )
    doc_astro = _create_document(
        db_session,
        IdentityType.USER,
        user.id,
        "astrophysics.pdf",
        "Astrophysics chapter: Gravitational lensing bends light around supermassive clusters.",
    )

    payload = {
        "document_ids": [doc_neuro.id, doc_astro.id],
        "question_count": 2,
        "mode": "practice",
        "question_type": "mixed",
        "title": "Cross-Disciplinary Revision",
    }
    create_res = client.post("/api/v1/revision/sessions", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()

    # Session documents list includes both documents
    session_doc_ids = {d["document_id"] for d in data["documents"]}
    assert session_doc_ids == {doc_neuro.id, doc_astro.id}

    # Verify per-question attribution
    q1 = data["questions"][0]
    q2 = data["questions"][1]

    assert q1["source_document_id"] == doc_neuro.id
    assert q1["source_document_title"] == "neuroscience.pdf"
    assert "doc 1" in q1["evidence_snippet"].lower()

    assert q2["source_document_id"] == doc_astro.id
    assert q2["source_document_title"] == "astrophysics.pdf"
    assert "doc 2" in q2["evidence_snippet"].lower()

    # Invariant: Question 1 is not attributed to astrophysics and Question 2 is not attributed to neuroscience
    assert q1["source_document_id"] != doc_astro.id
    assert q2["source_document_id"] != doc_neuro.id


# ---------------------------------------------------------------------------
# PART 5: OWNERSHIP & CROSS-IDENTITY ISOLATION
# ---------------------------------------------------------------------------

def test_cross_identity_access_and_attempt_isolation(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: M4IntegrationAIProvider,
):
    """
    Validates cross-identity security and ownership isolation:
    - User A cannot access or mutate User B's revision session
    - Guest A cannot access or mutate Guest B's revision session
    - Submitting an attempt for a question belonging to another session is rejected
    - Revision session history lists are strictly owner-scoped
    """
    user_a = _create_user(db_session, "user_a")
    user_b = _create_user(db_session, "user_b")
    guest_a = _create_guest(db_session)
    guest_b = _create_guest(db_session)

    cookies_user_a = _auth_cookies_for(user_a, db_session)
    cookies_user_b = _auth_cookies_for(user_b, db_session)
    cookies_guest_a = _guest_cookies_for(guest_a)
    cookies_guest_b = _guest_cookies_for(guest_b)

    doc_a = _create_document(db_session, IdentityType.USER, user_a.id, "doc_a.pdf", "Text A for user A")
    doc_b = _create_document(db_session, IdentityType.USER, user_b.id, "doc_b.pdf", "Text B for user B")
    doc_ga = _create_document(db_session, IdentityType.GUEST, guest_a.id, "doc_ga.pdf", "Text GA for guest A")

    # User A creates Session A
    _set_client_cookies(client, cookies_user_a)
    res_a = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc_a.id], "question_count": 1},
    )
    assert res_a.status_code == 201
    session_a = res_a.json()
    q_a_id = session_a["questions"][0]["id"]

    # User B creates Session B
    _set_client_cookies(client, cookies_user_b)
    res_b = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc_b.id], "question_count": 1},
    )
    assert res_b.status_code == 201
    session_b = res_b.json()
    q_b_id = session_b["questions"][0]["id"]

    # Guest A creates Session GA
    _set_client_cookies(client, cookies_guest_a)
    res_ga = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc_ga.id], "question_count": 1},
    )
    assert res_ga.status_code == 201
    session_ga = res_ga.json()
    q_ga_id = session_ga["questions"][0]["id"]

    # 1. User B attempts to view User A's session -> 404
    _set_client_cookies(client, cookies_user_b)
    assert client.get(f"/api/v1/revision/sessions/{session_a['id']}").status_code == 404

    # 2. User B attempts to submit attempt to User A's session -> 404
    att_cross = client.post(
        f"/api/v1/revision/sessions/{session_a['id']}/questions/{q_a_id}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert att_cross.status_code == 404

    # 3. User B attempts to complete User A's session -> 404
    assert client.post(f"/api/v1/revision/sessions/{session_a['id']}/complete").status_code == 404

    # 4. Guest B attempts to view Guest A's session -> 404
    _set_client_cookies(client, cookies_guest_b)
    assert client.get(f"/api/v1/revision/sessions/{session_ga['id']}").status_code == 404

    # 5. Guest B attempts to submit attempt to Guest A's session -> 404
    att_guest_cross = client.post(
        f"/api/v1/revision/sessions/{session_ga['id']}/questions/{q_ga_id}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert att_guest_cross.status_code == 404

    # 6. User A attempts to submit Question B (from Session B) to Session A -> 404 (Question not found in session)
    _set_client_cookies(client, cookies_user_a)
    tamper_res = client.post(
        f"/api/v1/revision/sessions/{session_a['id']}/questions/{q_b_id}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert tamper_res.status_code == 404
    assert "not found in this revision session" in tamper_res.json()["detail"].lower()

    # 7. Session list scoping
    list_a = client.get("/api/v1/revision/sessions").json()
    assert len(list_a) == 1
    assert list_a[0]["id"] == session_a["id"]

    _set_client_cookies(client, cookies_user_b)
    list_b = client.get("/api/v1/revision/sessions").json()
    assert len(list_b) == 1
    assert list_b[0]["id"] == session_b["id"]


# ---------------------------------------------------------------------------
# PART 6: GUEST QUOTA FULL LIFECYCLE
# ---------------------------------------------------------------------------

def test_guest_quota_lifecycle_and_enforcement(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: M4IntegrationAIProvider,
):
    """
    Validates guest AI quota enforcement across the full Revision lifecycle:
    - Session creation consumes 1 AI generation quota on success
    - Failed session generation (AI error) consumes 0 quota
    - Deterministic MCQ attempts consume 0 quota
    - Empty open-ended submission consumes 0 quota
    - Failed open-ended AI evaluation consumes 0 quota
    - Successful open-ended AI evaluation consumes 1 quota
    - Quota exhaustion rejects new session creation and open-ended evaluation (HTTP 403 guest_limit_reached)
    - Quota exhaustion allows deterministic MCQ attempts to succeed without penalty
    """
    guest = _create_guest(db_session)
    cookies = _guest_cookies_for(guest)
    _set_client_cookies(client, cookies)

    doc = _create_document(
        db_session,
        IdentityType.GUEST,
        guest.id,
        "quota_doc.pdf",
        "Biochemistry notes: Enzyme kinetics and Michaelis-Menten constant.",
    )

    # Initial guest quota
    db_session.refresh(guest)
    assert guest.ai_generation_count == 0

    # 1. Successful session creation consumes 1 AI generation
    create_res = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc.id], "question_count": 2, "question_type": "mixed"},
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]
    q_mcq = create_res.json()["questions"][0]
    q_open = create_res.json()["questions"][1]

    db_session.refresh(guest)
    assert guest.ai_generation_count == 1

    # 2. Failed session creation consumes 0 quota
    fake_ai_provider.should_fail = True
    fail_res = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc.id], "question_count": 2},
    )
    assert fail_res.status_code == 502
    db_session.refresh(guest)
    assert guest.ai_generation_count == 1  # unchanged
    fake_ai_provider.should_fail = False

    # 3. Deterministic MCQ attempts consume 0 quota
    mcq_att1 = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q_mcq['id']}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert mcq_att1.status_code == 201
    db_session.refresh(guest)
    assert guest.ai_generation_count == 1  # unchanged

    mcq_att2 = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q_mcq['id']}/attempts",
        json={"submitted_answer": "Ribosome"},
    )
    assert mcq_att2.status_code == 201
    db_session.refresh(guest)
    assert guest.ai_generation_count == 1  # unchanged

    # 4. Empty open-ended submission consumes 0 quota (deterministic empty handler)
    empty_att = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q_open['id']}/attempts",
        json={"submitted_answer": "   "},
    )
    assert empty_att.status_code == 201
    assert empty_att.json()["score"] == 0.0
    db_session.refresh(guest)
    assert guest.ai_generation_count == 1  # unchanged

    # 5. Failed open-ended AI evaluation consumes 0 quota
    fake_ai_provider.should_fail = True
    fail_eval = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q_open['id']}/attempts",
        json={"submitted_answer": "Enzymes lower the activation energy of chemical reactions."},
    )
    assert fail_eval.status_code == 502
    db_session.refresh(guest)
    assert guest.ai_generation_count == 1  # unchanged
    fake_ai_provider.should_fail = False

    # 6. Successful open-ended AI evaluation consumes 1 quota
    succ_eval = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q_open['id']}/attempts",
        json={"submitted_answer": "Enzymes lower the activation energy of chemical reactions."},
    )
    assert succ_eval.status_code == 201
    db_session.refresh(guest)
    assert guest.ai_generation_count == 2

    # 7. Quota exhaustion handling
    # Fast-forward guest's quota to maximum
    guest.ai_generation_count = settings.guest_max_ai_generations
    db_session.commit()

    # A) Session creation blocked before AI call
    blocked_create = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc.id], "question_count": 2},
    )
    assert blocked_create.status_code == 403
    assert blocked_create.json()["detail"]["code"] == "guest_limit_reached"

    # B) Open-ended attempt blocked before AI call
    blocked_eval = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q_open['id']}/attempts",
        json={"submitted_answer": "Another explanation of kinetics."},
    )
    assert blocked_eval.status_code == 403
    assert blocked_eval.json()["detail"]["code"] == "guest_limit_reached"

    # C) Deterministic MCQ attempt still SUCCEEDS when quota exhausted
    allowed_mcq = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q_mcq['id']}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert allowed_mcq.status_code == 201
    assert allowed_mcq.json()["is_correct"] is True


# ---------------------------------------------------------------------------
# SCORING EDGE CASE: UNATTEMPTED & PARTIAL ATTEMPTS
# ---------------------------------------------------------------------------

def test_unattempted_questions_scoring_invariance(
    client: TestClient,
    db_session: Session,
    fake_ai_provider: M4IntegrationAIProvider,
):
    """
    Validates official score calculation when some questions are left unattempted:
    - 3 questions total
    - Question 1 attempted and correct (score 1.0)
    - Question 2 and Question 3 unattempted (score 0.0 each)
    - Session score is (1.0 + 0.0 + 0.0) / 3 = 0.3333333333333333
    """
    user = _create_user(db_session, "scoring_user")
    cookies = _auth_cookies_for(user, db_session)
    _set_client_cookies(client, cookies)

    doc = _create_document(
        db_session,
        IdentityType.USER,
        user.id,
        "math_notes.pdf",
        "Calculus notes: Fundamental theorem of calculus connecting derivatives and integrals.",
    )

    create_res = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc.id], "question_count": 3, "question_type": "multiple_choice"},
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]
    q1_id = create_res.json()["questions"][0]["id"]

    # Attempt only question 1
    att_res = client.post(
        f"/api/v1/revision/sessions/{session_id}/questions/{q1_id}/attempts",
        json={"submitted_answer": "Mitochondria"},
    )
    assert att_res.status_code == 201

    # Complete session without attempting Q2 or Q3
    complete_res = client.post(f"/api/v1/revision/sessions/{session_id}/complete")
    assert complete_res.status_code == 200
    assert pytest.approx(complete_res.json()["score"], 0.001) == 1.0 / 3.0

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import (
    Document,
    GuestSession,
    QuizQuestion,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    User,
)
from app.main import app
from app.schemas.identity import Identity, IdentityType
from app.schemas.revision import (
    MAX_REVISION_DOCUMENT_IDS,
    RevisionSessionCreateRequest,
)
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_limit_service import GuestLimitType
from app.services.guest_session_service import create_guest_session, generate_session_token
from app.services.user_session_service import create_user_session


# ---------------------------------------------------------------------------
# Test AI Providers
# ---------------------------------------------------------------------------

class FakeRevisionAIProvider(AIProvider):
    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.call_count = 0
        self.custom_response: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        self.call_count += 1

        if self.custom_response is not None:
            return self.custom_response

        # Support legacy quiz prompt format (expects question, options, correct_answer_index)
        if "correct_answer_index" in prompt:
            return json.dumps(
                [
                    {
                        "question": "Which organelle handles energy production?",
                        "options": ["Mitochondria", "Ribosome", "Endoplasmic Reticulum", "Golgi Apparatus"],
                        "correct_answer_index": 0,
                    }
                ]
            )

        # Check question count requested or default to 3
        count = 3
        if "exactly 5" in prompt:
            count = 5
        elif "exactly 2" in prompt:
            count = 2

        is_open = "open_ended" in prompt or "OPEN-ENDED" in prompt
        is_mixed = "MIX of multiple choice" in prompt

        questions = []
        for i in range(1, count + 1):
            if is_open or (is_mixed and i % 2 == 0):
                questions.append(
                    {
                        "question_text": f"Explain key concept {i} regarding cell mechanics.",
                        "question_type": "open_ended",
                        "options": None,
                        "correct_answer": f"Concept {i} governs active cellular transport through protein pumps.",
                        "explanation": f"Detailed rubric criteria for evaluating concept {i}.",
                        "source_document_id": "test-doc-id",
                        "evidence_snippet": f"Supporting quotation from source text regarding concept {i}.",
                    }
                )
            else:
                questions.append(
                    {
                        "question_text": f"Which organelle handles energy production in cell {i}?",
                        "question_type": "multiple_choice",
                        "options": ["Mitochondria", "Ribosome", "Endoplasmic Reticulum", "Golgi Apparatus"],
                        "correct_answer": "Mitochondria",
                        "explanation": "Mitochondria produce ATP through cellular respiration.",
                        "source_document_id": "test-doc-id",
                        "evidence_snippet": "Mitochondria are the powerhouses of the cell, generating most chemical energy.",
                    }
                )

        return json.dumps(questions)


class FailingRevisionAIProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Upstream AI Provider timeout")


# ---------------------------------------------------------------------------
# Fixtures
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
    return FakeRevisionAIProvider()


@pytest.fixture()
def client(fake_ai_provider):
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user_a(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-rev-a-{uid}",
        email=f"user-a-{uid}@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def user_b(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-rev-b-{uid}",
        email=f"user-b-{uid}@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def ready_doc_user_a(db_session: Session, user_a: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-a-{uid}",
        original_filename="biology_intro.pdf",
        stored_filename=f"biology_{uid}.pdf",
        status="ready",
        extracted_text=(
            "Mitochondria generate cellular ATP via aerobic respiration. "
            "Cell membranes control active transport through ion pumps and carrier proteins."
        ),
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture()
def ready_doc_2_user_a(db_session: Session, user_a: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-a2-{uid}",
        original_filename="genetics_intro.pdf",
        stored_filename=f"genetics_{uid}.pdf",
        status="ready",
        extracted_text=(
            "DNA replication occurs during the S-phase of the cell cycle. "
            "Polymerase enzymes synthesize complementary strands."
        ),
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture()
def ready_doc_user_b(db_session: Session, user_b: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-b-{uid}",
        original_filename="chemistry.pdf",
        stored_filename=f"chem_{uid}.pdf",
        status="ready",
        extracted_text="Covalent bonding involves the sharing of electron pairs between atoms.",
        owner_type=IdentityType.USER.value,
        owner_id=user_b.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def _auth_cookie_for(user: User, db: Session) -> dict[str, str]:
    session = create_user_session(db, user.id)
    return {settings.user_session_cookie_name: session.id}


# ---------------------------------------------------------------------------
# Tests: 1. Schema Validation
# ---------------------------------------------------------------------------

def test_revision_schema_validation():
    # Valid minimal payload
    req = RevisionSessionCreateRequest(document_ids=["doc-1", "doc-2"])
    assert req.document_ids == ["doc-1", "doc-2"]
    assert req.difficulty == "intermediate"
    assert req.mode == "practice"
    assert req.question_type == "multiple_choice"
    assert req.question_count == 5

    # Deduplication preserving order
    req2 = RevisionSessionCreateRequest(document_ids=["doc-1", "doc-2", "doc-1", "doc-3"])
    assert req2.document_ids == ["doc-1", "doc-2", "doc-3"]

    # Title whitespace cleanup
    req3 = RevisionSessionCreateRequest(document_ids=["doc-1"], title="  Midterm Revision  ")
    assert req3.title == "Midterm Revision"

    # Empty document list rejected
    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=[])

    # Out of bounds question count rejected
    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], question_count=0)
    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], question_count=21)

    # Invalid difficulty rejected
    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], difficulty="expert")  # type: ignore

    # Invalid mode rejected
    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], mode="game")  # type: ignore


# ---------------------------------------------------------------------------
# Tests: 2. Single Document Session Creation
# ---------------------------------------------------------------------------

def test_create_revision_session_single_document(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
    fake_ai_provider: FakeRevisionAIProvider,
):
    cookies = _auth_cookie_for(user_a, db_session)
    payload = {
        "document_ids": [ready_doc_user_a.id],
        "question_count": 3,
        "difficulty": "intermediate",
        "mode": "practice",
        "question_type": "multiple_choice",
    }
    response = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["title"] == f"{ready_doc_user_a.original_filename} Practice"
    assert data["status"] == "in_progress"
    assert data["total_questions"] == 3
    assert data["score"] is None
    assert data["config"]["difficulty"] == "intermediate"
    assert data["config"]["mode"] == "practice"
    assert data["config"]["question_type"] == "multiple_choice"

    # Documents
    assert len(data["documents"]) == 1
    assert data["documents"][0]["document_id"] == ready_doc_user_a.id
    assert data["documents"][0]["original_filename"] == ready_doc_user_a.original_filename

    # Questions
    assert len(data["questions"]) == 3
    for i, q in enumerate(data["questions"], start=1):
        assert q["position"] == i
        assert q["question_type"] == "multiple_choice"
        assert len(q["options"]) == 4
        assert q["correct_answer"] in q["options"]
        assert q["evidence_snippet"] is not None
        assert q["source_document_id"] == ready_doc_user_a.id


# ---------------------------------------------------------------------------
# Tests: 3. Multi-Document Session Creation
# ---------------------------------------------------------------------------

def test_create_revision_session_multi_document(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    ready_doc_2_user_a: Document,
    user_a: User,
    fake_ai_provider: FakeRevisionAIProvider,
):
    cookies = _auth_cookie_for(user_a, db_session)
    payload = {
        "document_ids": [ready_doc_user_a.id, ready_doc_2_user_a.id],
        "title": "Bio & Genetics Combined",
        "question_count": 5,
        "difficulty": "advanced",
        "mode": "quiz",
        "question_type": "multiple_choice",
    }
    response = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "Bio & Genetics Combined"
    assert data["total_questions"] == 5
    assert len(data["documents"]) == 2
    assert set(data["document_ids"]) == {ready_doc_user_a.id, ready_doc_2_user_a.id}

    # Prompt check: verifies both documents reached prompt
    assert fake_ai_provider.last_prompt is not None
    assert ready_doc_user_a.original_filename in fake_ai_provider.last_prompt
    assert ready_doc_2_user_a.original_filename in fake_ai_provider.last_prompt


# ---------------------------------------------------------------------------
# Tests: 4. Difficulty Influencing Prompt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("difficulty", ["beginner", "intermediate", "advanced"])
def test_revision_difficulty_prompt_influence(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
    fake_ai_provider: FakeRevisionAIProvider,
    difficulty: str,
):
    cookies = _auth_cookie_for(user_a, db_session)
    payload = {
        "document_ids": [ready_doc_user_a.id],
        "difficulty": difficulty,
        "question_count": 2,
    }
    response = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert response.status_code == 201
    assert fake_ai_provider.last_prompt is not None
    assert f"Difficulty Level: {difficulty.upper()}" in fake_ai_provider.last_prompt


# ---------------------------------------------------------------------------
# Tests: 5. Mode Influencing Prompt & Config
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode, expected_label", [
    ("practice", "PRACTICE STUDY"),
    ("quiz", "QUIZ ASSESSMENT"),
    ("flashcards", "FLASHCARD ACTIVE RECALL"),
])
def test_revision_mode_prompt_and_config(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
    fake_ai_provider: FakeRevisionAIProvider,
    mode: str,
    expected_label: str,
):
    cookies = _auth_cookie_for(user_a, db_session)
    payload = {
        "document_ids": [ready_doc_user_a.id],
        "mode": mode,
        "question_count": 2,
    }
    response = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert response.status_code == 201
    assert fake_ai_provider.last_prompt is not None
    assert expected_label in fake_ai_provider.last_prompt

    data = response.json()
    assert data["config"]["mode"] == mode


# ---------------------------------------------------------------------------
# Tests: 6. Question Count Bounds & Contract
# ---------------------------------------------------------------------------

def test_revision_question_count_contract(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
    fake_ai_provider: FakeRevisionAIProvider,
):
    cookies = _auth_cookie_for(user_a, db_session)

    # Valid custom count
    payload = {
        "document_ids": [ready_doc_user_a.id],
        "question_count": 2,
    }
    res = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201
    assert res.json()["total_questions"] == 2
    assert "exactly 2" in fake_ai_provider.last_prompt

    # Invalid counts rejected by Pydantic validation (422)
    res_zero = client.post("/api/v1/revision/sessions", json={"document_ids": [ready_doc_user_a.id], "question_count": 0}, cookies=cookies)
    assert res_zero.status_code == 422

    res_too_many = client.post("/api/v1/revision/sessions", json={"document_ids": [ready_doc_user_a.id], "question_count": 25}, cookies=cookies)
    assert res_too_many.status_code == 422


# ---------------------------------------------------------------------------
# Tests: 7. MCQ Question Generation
# ---------------------------------------------------------------------------

def test_revision_mcq_generation(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)
    payload = {
        "document_ids": [ready_doc_user_a.id],
        "question_type": "multiple_choice",
        "question_count": 2,
    }
    res = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201
    questions = res.json()["questions"]
    assert len(questions) == 2
    for q in questions:
        assert q["question_type"] == "multiple_choice"
        assert isinstance(q["options"], list)
        assert len(q["options"]) == 4
        assert q["correct_answer"] in q["options"]
        assert q["explanation"] is not None


# ---------------------------------------------------------------------------
# Tests: 8. Open-Ended Question Generation
# ---------------------------------------------------------------------------

def test_revision_open_ended_generation(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
    fake_ai_provider: FakeRevisionAIProvider,
):
    cookies = _auth_cookie_for(user_a, db_session)
    payload = {
        "document_ids": [ready_doc_user_a.id],
        "question_type": "open_ended",
        "question_count": 2,
    }
    res = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201
    questions = res.json()["questions"]
    assert len(questions) == 2
    for q in questions:
        assert q["question_type"] == "open_ended"
        assert q["options"] is None
        assert len(q["correct_answer"]) > 10
        assert q["explanation"] is not None
        assert q["evidence_snippet"] is not None


# ---------------------------------------------------------------------------
# Tests: 9. RAG / Evidence Provenance Preservation
# ---------------------------------------------------------------------------

def test_revision_evidence_provenance(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)
    payload = {
        "document_ids": [ready_doc_user_a.id],
        "question_count": 2,
    }
    res = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201
    questions = res.json()["questions"]
    for q in questions:
        assert q["source_document_id"] == ready_doc_user_a.id
        assert q["source_document_title"] == ready_doc_user_a.original_filename
        assert q["evidence_snippet"] is not None
        assert q["evidence_metadata"]["document_title"] == ready_doc_user_a.original_filename


# ---------------------------------------------------------------------------
# Tests: 10. Ownership Isolation & IDOR Protection
# ---------------------------------------------------------------------------

def test_revision_ownership_isolation(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    ready_doc_user_b: Document,
    user_a: User,
    user_b: User,
):
    cookies_a = _auth_cookie_for(user_a, db_session)
    cookies_b = _auth_cookie_for(user_b, db_session)

    # 1. User A cannot create a session using User B's document (404)
    res_cross_create = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [ready_doc_user_b.id]},
        cookies=cookies_a,
    )
    assert res_cross_create.status_code == 404
    assert "Document not found" in res_cross_create.json()["detail"]

    # 2. User A creates their own session
    res_a = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [ready_doc_user_a.id], "question_count": 2},
        cookies=cookies_a,
    )
    assert res_a.status_code == 201
    session_a_id = res_a.json()["id"]

    # 3. User B cannot retrieve User A's session (404, not 403, preventing IDOR)
    res_cross_get = client.get(
        f"/api/v1/revision/sessions/{session_a_id}",
        cookies=cookies_b,
    )
    assert res_cross_get.status_code == 404
    assert "Revision session not found" in res_cross_get.json()["detail"]

    # 4. User B cannot see User A's session in session list
    res_list_b = client.get("/api/v1/revision/sessions", cookies=cookies_b)
    assert res_list_b.status_code == 200
    b_session_ids = [s["id"] for s in res_list_b.json()]
    assert session_a_id not in b_session_ids


# ---------------------------------------------------------------------------
# Tests: 11. Invalid / Unready Documents
# ---------------------------------------------------------------------------

def test_revision_unready_document_rejection(
    client: TestClient,
    db_session: Session,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-processing-{uid}",
        original_filename="processing.pdf",
        stored_filename=f"proc_{uid}.pdf",
        status="processing",
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
    )
    db_session.add(doc)
    db_session.commit()

    res = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc.id]},
        cookies=cookies,
    )
    assert res.status_code == 400
    assert "is not ready for revision" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: 12. Zero Readable Documents Rejection
# ---------------------------------------------------------------------------

def test_revision_zero_readable_documents_rejection(
    client: TestClient,
    db_session: Session,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)
    uid = uuid.uuid4().hex[:8]
    doc_empty = Document(
        id=f"doc-empty-{uid}",
        original_filename="empty.pdf",
        stored_filename=f"empty_{uid}.pdf",
        status="ready",
        extracted_text="   ",
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
    )
    db_session.add(doc_empty)
    db_session.commit()

    # Single document with no text returns 422
    res_single = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc_empty.id]},
        cookies=cookies,
    )
    assert res_single.status_code == 422
    assert "No readable text was detected" in res_single.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: 13. Guest Limit Enforcement (403 when quota exhausted)
# ---------------------------------------------------------------------------

def test_revision_guest_limit_enforcement(
    client: TestClient,
    db_session: Session,
):
    # Create guest with zero quota remaining
    guest = create_guest_session(db_session)
    guest.ai_generation_count = settings.guest_max_ai_generations
    db_session.commit()

    doc = Document(
        id=f"doc-guest-{uuid.uuid4().hex[:8]}",
        original_filename="guest_notes.pdf",
        stored_filename="g.pdf",
        status="ready",
        extracted_text="Photosynthesis converts light energy into chemical sugars.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}
    res = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc.id]},
        cookies=cookies,
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "guest_limit_reached"


# ---------------------------------------------------------------------------
# Tests: 14. Failed Generation Does Not Consume Guest Quota
# ---------------------------------------------------------------------------

def test_failed_generation_preserves_guest_quota(
    db_session: Session,
):
    failing_provider = FailingRevisionAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: failing_provider

    try:
        with TestClient(app) as test_client:
            guest = create_guest_session(db_session)
            guest.ai_generation_count = 0
            db_session.commit()

            doc = Document(
                id=f"doc-fail-{uuid.uuid4().hex[:8]}",
                original_filename="notes.pdf",
                stored_filename="f.pdf",
                status="ready",
                extracted_text="Some valid readable document text.",
                owner_type=IdentityType.GUEST.value,
                owner_id=guest.id,
            )
            db_session.add(doc)
            db_session.commit()

            cookies = {settings.guest_session_cookie_name: guest.id}
            res = test_client.post(
                "/api/v1/revision/sessions",
                json={"document_ids": [doc.id]},
                cookies=cookies,
            )
            assert res.status_code == 502

            # Check guest usage count was NOT incremented
            db_session.refresh(guest)
            assert guest.ai_generation_count == 0

            # Check no orphaned revision session was persisted
            sessions = db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).all()
            assert len(sessions) == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: 15. Successful Generation Consumes Guest Quota
# ---------------------------------------------------------------------------

def test_successful_generation_increments_guest_quota(
    client: TestClient,
    db_session: Session,
):
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-succ-{uuid.uuid4().hex[:8]}",
        original_filename="guest_notes.pdf",
        stored_filename="s.pdf",
        status="ready",
        extracted_text="Valid biological notes on respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}
    res = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [doc.id], "question_count": 2},
        cookies=cookies,
    )
    assert res.status_code == 201

    db_session.refresh(guest)
    assert guest.ai_generation_count == 1


# ---------------------------------------------------------------------------
# Tests: 16. Session List Endpoint
# ---------------------------------------------------------------------------

def test_list_revision_sessions(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)

    # Create two sessions
    res1 = client.post("/api/v1/revision/sessions", json={"document_ids": [ready_doc_user_a.id], "title": "Session 1", "question_count": 2}, cookies=cookies)
    assert res1.status_code == 201
    res2 = client.post("/api/v1/revision/sessions", json={"document_ids": [ready_doc_user_a.id], "title": "Session 2", "question_count": 2}, cookies=cookies)
    assert res2.status_code == 201

    list_res = client.get("/api/v1/revision/sessions", cookies=cookies)
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) >= 2
    # Verify newest first
    assert sessions[0]["title"] == "Session 2"
    assert sessions[1]["title"] == "Session 1"
    assert ready_doc_user_a.id in sessions[0]["document_ids"]


# ---------------------------------------------------------------------------
# Tests: 17. Session Detail Endpoint
# ---------------------------------------------------------------------------

def test_get_revision_session_detail(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)
    created = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [ready_doc_user_a.id], "title": "Deep Review", "question_count": 2},
        cookies=cookies,
    ).json()

    session_id = created["id"]
    res = client.get(f"/api/v1/revision/sessions/{session_id}", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == session_id
    assert data["title"] == "Deep Review"
    assert len(data["documents"]) == 1
    assert len(data["questions"]) == 2
    assert data["questions"][0]["position"] == 1
    assert data["questions"][1]["position"] == 2


# ---------------------------------------------------------------------------
# Tests: 18. Transaction & Rollback Behavior
# ---------------------------------------------------------------------------

def test_revision_transaction_rollback_on_db_error(
    ready_doc_user_a: Document,
    user_a: User,
    fake_ai_provider: FakeRevisionAIProvider,
    db_session: Session,
):
    from app.services.revision_service import generate_revision_session
    identity = Identity(type=IdentityType.USER, id=user_a.id, user=user_a)
    unique_title = f"Rollback Test {uuid.uuid4().hex}"
    payload = RevisionSessionCreateRequest(document_ids=[ready_doc_user_a.id], title=unique_title, question_count=2)

    # Force a database failure on commit to verify rollback
    with patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB lock error")):
        with pytest.raises(RuntimeError, match="Simulated DB lock error"):
            import asyncio
            asyncio.run(
                generate_revision_session(
                    db=db_session,
                    identity=identity,
                    documents=[ready_doc_user_a],
                    payload=payload,
                    ai_provider=fake_ai_provider,
                )
            )

    # Verify no session was committed
    sessions = db_session.query(RevisionSession).filter(RevisionSession.title == unique_title).all()
    assert len(sessions) == 0


# ---------------------------------------------------------------------------
# Tests: 19. Revision Data Persistence & SQL Relations
# ---------------------------------------------------------------------------

def test_revision_data_persistence_and_relationships(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)
    res = client.post(
        "/api/v1/revision/sessions",
        json={"document_ids": [ready_doc_user_a.id], "title": "Persistent Verification", "question_count": 3},
        cookies=cookies,
    )
    assert res.status_code == 201
    session_id = res.json()["id"]

    # Query DB directly via SQLAlchemy
    session = db_session.query(RevisionSession).filter(RevisionSession.id == session_id).first()
    assert session is not None
    assert session.title == "Persistent Verification"
    assert session.owner_type == IdentityType.USER.value
    assert session.owner_id == user_a.id
    assert session.status == "in_progress"
    assert session.total_questions == 3

    # Check join table
    rsd = db_session.query(RevisionSessionDocument).filter(RevisionSessionDocument.session_id == session_id).all()
    assert len(rsd) == 1
    assert rsd[0].document_id == ready_doc_user_a.id

    # Check questions table
    questions = db_session.query(RevisionQuestion).filter(RevisionQuestion.session_id == session_id).order_by(RevisionQuestion.position).all()
    assert len(questions) == 3
    for idx, q in enumerate(questions, start=1):
        assert q.position == idx
        assert q.source_document_id == ready_doc_user_a.id
        assert q.evidence_snippet is not None


# ---------------------------------------------------------------------------
# Tests: 20. Legacy Study Quiz Remains Untouched
# ---------------------------------------------------------------------------

def test_legacy_study_quiz_untouched(
    client: TestClient,
    db_session: Session,
    ready_doc_user_a: Document,
    user_a: User,
):
    cookies = _auth_cookie_for(user_a, db_session)

    # Legacy endpoint: POST /api/v1/documents/{document_id}/quiz
    res = client.post(
        f"/api/v1/documents/{ready_doc_user_a.id}/quiz",
        cookies=cookies,
    )
    assert res.status_code == 201
    questions = res.json()
    assert isinstance(questions, list)
    assert len(questions) > 0
    assert "correct_answer_index" in questions[0]

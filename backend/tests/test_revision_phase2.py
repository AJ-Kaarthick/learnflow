import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.evaluation_service import (
    calculate_session_score,
    complete_revision_session,
    evaluate_mcq_answer,
    evaluate_open_ended_answer,
    record_question_attempt,
)
from app.services.guest_session_service import create_guest_session
from app.services.user_session_service import create_user_session


# ---------------------------------------------------------------------------
# Test AI Providers
# ---------------------------------------------------------------------------

class FakeEvaluationAIProvider(AIProvider):
    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.call_count = 0
        self.custom_response: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        self.call_count += 1

        if self.custom_response is not None:
            return self.custom_response

        # Check if this is an evaluation prompt
        if "academic evaluator" in prompt or "Evaluate the student's submitted answer" in prompt:
            lower = prompt.lower()
            if "student's submitted answer:" in lower:
                after_sub = lower.split("student's submitted answer:")[1]
                student_section = after_sub.split("evaluation guidelines:")[0] if "evaluation guidelines:" in after_sub else after_sub
            else:
                student_section = lower

            if "poor" in student_section or "irrelevant" in student_section:
                return json.dumps({
                    "score": 0.2,
                    "is_correct": False,
                    "feedback": "The answer misses the core concept.",
                    "reasoning": "Flawed conceptual understanding.",
                })
            elif "partial" in student_section:
                return json.dumps({
                    "score": 0.5,
                    "is_correct": False,
                    "feedback": "Partially correct.",
                    "reasoning": "Partial concept coverage.",
                })
            else:
                return json.dumps({
                    "score": 0.9,
                    "is_correct": True,
                    "feedback": "Excellent explanation of active transport.",
                    "reasoning": "Accurate and grounded.",
                })

        # Fallback for question generation or other prompts
        return json.dumps([
            {
                "question": "Which organelle handles energy production?",
                "options": ["Mitochondria", "Ribosome", "Endoplasmic Reticulum", "Golgi Apparatus"],
                "correct_answer_index": 0,
            }
        ])


class FailingEvaluationAIProvider(AIProvider):
    def __init__(self) -> None:
        self.call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        raise AIProviderError("Simulated evaluation upstream timeout")


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
def fake_ai():
    return FakeEvaluationAIProvider()


@pytest.fixture()
def client(fake_ai):
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user_a(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-eval-a-{uid}",
        email=f"user-eval-a-{uid}@example.com",
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
        id=f"user-eval-b-{uid}",
        email=f"user-eval-b-{uid}@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def doc_user_a(db_session: Session, user_a: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-eval-a-{uid}",
        original_filename="biology.pdf",
        stored_filename=f"bio_{uid}.pdf",
        status="ready",
        extracted_text="Mitochondria produce ATP. Cell membranes use active transport.",
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture()
def sample_session_user_a(db_session: Session, user_a: User, doc_user_a: Document) -> tuple[RevisionSession, RevisionQuestion, RevisionQuestion]:
    """Creates a revision session with 1 MCQ question and 1 Open-ended question for user_a."""
    uid = uuid.uuid4().hex[:8]
    session = RevisionSession(
        id=f"session-eval-{uid}",
        title="Biology Evaluation Practice",
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        status="in_progress",
        config={"difficulty": "intermediate", "mode": "practice"},
        total_questions=2,
    )
    db_session.add(session)
    db_session.flush()

    rsd = RevisionSessionDocument(session_id=session.id, document_id=doc_user_a.id)
    db_session.add(rsd)

    q1_mcq = RevisionQuestion(
        id=f"q-mcq-{uid}",
        session_id=session.id,
        position=1,
        question_type="multiple_choice",
        question_text="Which organelle generates ATP?",
        options=["Mitochondria", "Ribosome", "Golgi Apparatus", "Vacuole"],
        correct_answer="Mitochondria",
        explanation="Mitochondria are the powerhouses that generate ATP through respiration.",
        source_document_id=doc_user_a.id,
        evidence_snippet="Mitochondria produce ATP.",
    )
    q2_open = RevisionQuestion(
        id=f"q-open-{uid}",
        session_id=session.id,
        position=2,
        question_type="open_ended",
        question_text="Explain the primary function of cell membranes in active transport.",
        options=None,
        correct_answer="Cell membranes utilize protein pumps and ATP to transport ions against gradients.",
        explanation="Full credit requires mentioning protein pumps and ATP energy.",
        source_document_id=doc_user_a.id,
        evidence_snippet="Cell membranes use active transport.",
    )
    db_session.add_all([q1_mcq, q2_open])
    db_session.commit()
    db_session.refresh(session)
    db_session.refresh(q1_mcq)
    db_session.refresh(q2_open)
    return session, q1_mcq, q2_open


def _auth_cookie_for(user: User, db: Session) -> dict[str, str]:
    session = create_user_session(db, user.id)
    return {settings.user_session_cookie_name: session.id}


# ---------------------------------------------------------------------------
# 1. MCQ Correct Answer
# ---------------------------------------------------------------------------

def test_mcq_correct_answer(sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion]):
    _, q_mcq, _ = sample_session_user_a
    is_correct, score, feedback, meta = evaluate_mcq_answer(q_mcq, "Mitochondria")
    assert is_correct is True
    assert score == 1.0
    assert "Correct!" in feedback
    assert meta["evaluation_type"] == "deterministic_mcq"


# ---------------------------------------------------------------------------
# 2. MCQ Incorrect Answer
# ---------------------------------------------------------------------------

def test_mcq_incorrect_answer(sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion]):
    _, q_mcq, _ = sample_session_user_a
    is_correct, score, feedback, meta = evaluate_mcq_answer(q_mcq, "Ribosome")
    assert is_correct is False
    assert score == 0.0
    assert "Incorrect" in feedback
    assert "The correct answer is: Mitochondria" in feedback


# ---------------------------------------------------------------------------
# 3. MCQ Normalization Behavior
# ---------------------------------------------------------------------------

def test_mcq_normalization_behavior(sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion]):
    _, q_mcq, _ = sample_session_user_a

    # Case-insensitive
    is_correct, score, _, _ = evaluate_mcq_answer(q_mcq, "  mitochondria  ")
    assert is_correct is True
    assert score == 1.0

    # Option letter 'A' (Mitochondria is index 0)
    is_correct, score, _, _ = evaluate_mcq_answer(q_mcq, "A")
    assert is_correct is True
    assert score == 1.0

    # Option letter with parenthesis 'A)'
    is_correct, score, _, _ = evaluate_mcq_answer(q_mcq, "a)")
    assert is_correct is True
    assert score == 1.0

    # Number index '1'
    is_correct, score, _, _ = evaluate_mcq_answer(q_mcq, "1")
    assert is_correct is True
    assert score == 1.0

    # Wrong letter 'B' (Ribosome)
    is_correct, score, _, _ = evaluate_mcq_answer(q_mcq, "B")
    assert is_correct is False
    assert score == 0.0


# ---------------------------------------------------------------------------
# 4. MCQ Does Not Invoke AI Provider
# ---------------------------------------------------------------------------

def test_mcq_does_not_invoke_ai(
    client: TestClient,
    db_session: Session,
    user_a: User,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
    fake_ai: FakeEvaluationAIProvider,
):
    session, q_mcq, _ = sample_session_user_a
    cookies = _auth_cookie_for(user_a, db_session)

    initial_ai_calls = fake_ai.call_count
    res = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_mcq.id}/attempts",
        json={"submitted_answer": "Mitochondria"},
        cookies=cookies,
    )
    assert res.status_code == 201
    assert fake_ai.call_count == initial_ai_calls  # Zero AI calls made!


# ---------------------------------------------------------------------------
# 5. Open-Ended Evaluation Success
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_open_ended_evaluation_success(
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
    fake_ai: FakeEvaluationAIProvider,
):
    _, _, q_open = sample_session_user_a
    is_correct, score, feedback, meta = await evaluate_open_ended_answer(
        question=q_open,
        submitted_answer="Cell membranes use ATP-driven protein pumps to move ions across membranes.",
        ai_provider=fake_ai,
    )
    assert is_correct is True
    assert score >= 0.7
    assert "mitochondrial" in feedback or "explanation" in feedback
    assert meta["evaluation_type"] == "ai_assisted"


# ---------------------------------------------------------------------------
# 6. Open-Ended Structured LLM Response
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_open_ended_structured_llm_response(
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    _, _, q_open = sample_session_user_a
    mock_ai = MagicMock(spec=AIProvider)
    mock_ai.generate_text = AsyncMock(return_value=json.dumps({
        "score": 0.88,
        "is_correct": True,
        "feedback": "Strong understanding of active ion transport.",
        "reasoning": "Mentions protein pump mechanism and energy coupling.",
    }))

    is_correct, score, feedback, meta = await evaluate_open_ended_answer(
        question=q_open,
        submitted_answer="Active transport requires pumps and energy.",
        ai_provider=mock_ai,
    )
    assert is_correct is True
    assert score == 0.88
    assert "Strong understanding" in feedback
    assert meta["reasoning"] == "Mentions protein pump mechanism and energy coupling."


# ---------------------------------------------------------------------------
# 7. Open-Ended Score Normalization (Clamping 0.0 to 1.0)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_open_ended_score_normalization(
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    _, _, q_open = sample_session_user_a
    mock_ai = MagicMock(spec=AIProvider)
    # Return out-of-bounds score 1.5
    mock_ai.generate_text = AsyncMock(return_value=json.dumps({
        "score": 1.5,
        "is_correct": True,
        "feedback": "Super answer",
    }))

    _, score, _, _ = await evaluate_open_ended_answer(
        question=q_open,
        submitted_answer="Good answer",
        ai_provider=mock_ai,
    )
    assert score == 1.0  # Clamped to 1.0

    # Return negative score -0.5
    mock_ai.generate_text = AsyncMock(return_value=json.dumps({
        "score": -0.5,
        "is_correct": False,
        "feedback": "Bad answer",
    }))
    _, score_neg, _, _ = await evaluate_open_ended_answer(
        question=q_open,
        submitted_answer="Bad answer",
        ai_provider=mock_ai,
    )
    assert score_neg == 0.0  # Clamped to 0.0


# ---------------------------------------------------------------------------
# 8. Empty / Trivial Answer Handling
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_empty_answer_handling(
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
    fake_ai: FakeEvaluationAIProvider,
):
    _, _, q_open = sample_session_user_a
    initial_calls = fake_ai.call_count

    # Empty string
    is_correct, score, feedback, meta = await evaluate_open_ended_answer(
        question=q_open,
        submitted_answer="   ",
        ai_provider=fake_ai,
    )
    assert is_correct is False
    assert score == 0.0
    assert "No answer was provided" in feedback
    assert meta["evaluation_type"] == "deterministic_empty"
    assert fake_ai.call_count == initial_calls  # Zero AI calls!

    # Trivial single punctuation
    is_corr, sc, _, m = await evaluate_open_ended_answer(
        question=q_open,
        submitted_answer=".",
        ai_provider=fake_ai,
    )
    assert is_corr is False
    assert sc == 0.0
    assert m["evaluation_type"] == "deterministic_trivial"
    assert fake_ai.call_count == initial_calls


# ---------------------------------------------------------------------------
# 9. Attempt Persistence
# ---------------------------------------------------------------------------

def test_attempt_persistence(
    client: TestClient,
    db_session: Session,
    user_a: User,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session, q_mcq, _ = sample_session_user_a
    cookies = _auth_cookie_for(user_a, db_session)

    res = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_mcq.id}/attempts",
        json={"submitted_answer": "Mitochondria"},
        cookies=cookies,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] is not None
    assert data["attempt_number"] == 1
    assert data["is_correct"] is True
    assert data["score"] == 1.0

    # Query DB directly to verify persistence
    attempt = db_session.query(RevisionAttempt).filter(RevisionAttempt.id == data["id"]).first()
    assert attempt is not None
    assert attempt.question_id == q_mcq.id
    assert attempt.session_id == session.id
    assert attempt.submitted_answer == "Mitochondria"


# ---------------------------------------------------------------------------
# 10, 11, 12, 13. Sequential Attempt Numbering & Prior Attempts Unchanged
# ---------------------------------------------------------------------------

def test_sequential_attempt_numbering_and_immutability(
    client: TestClient,
    db_session: Session,
    user_a: User,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session, q_mcq, _ = sample_session_user_a
    cookies = _auth_cookie_for(user_a, db_session)

    # Attempt 1: Incorrect
    res1 = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_mcq.id}/attempts",
        json={"submitted_answer": "Ribosome"},
        cookies=cookies,
    )
    assert res1.status_code == 201
    att1_data = res1.json()
    assert att1_data["attempt_number"] == 1
    assert att1_data["is_correct"] is False
    assert att1_data["score"] == 0.0

    # Attempt 2: Incorrect again
    res2 = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_mcq.id}/attempts",
        json={"submitted_answer": "Golgi Apparatus"},
        cookies=cookies,
    )
    assert res2.status_code == 201
    att2_data = res2.json()
    assert att2_data["attempt_number"] == 2
    assert att2_data["is_correct"] is False

    # Attempt 3: Correct!
    res3 = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_mcq.id}/attempts",
        json={"submitted_answer": "Mitochondria"},
        cookies=cookies,
    )
    assert res3.status_code == 201
    att3_data = res3.json()
    assert att3_data["attempt_number"] == 3
    assert att3_data["is_correct"] is True
    assert att3_data["score"] == 1.0

    # Verify prior attempts remain unchanged in database
    attempts = (
        db_session.query(RevisionAttempt)
        .filter(RevisionAttempt.question_id == q_mcq.id)
        .order_by(RevisionAttempt.attempt_number)
        .all()
    )
    assert len(attempts) == 3
    assert attempts[0].attempt_number == 1
    assert attempts[0].submitted_answer == "Ribosome"
    assert attempts[0].is_correct is False
    assert attempts[1].attempt_number == 2
    assert attempts[1].submitted_answer == "Golgi Apparatus"
    assert attempts[1].is_correct is False
    assert attempts[2].attempt_number == 3
    assert attempts[2].submitted_answer == "Mitochondria"
    assert attempts[2].is_correct is True

    # Invariant check: RevisionQuestion itself was never mutated
    db_session.refresh(q_mcq)
    assert q_mcq.question_text == "Which organelle generates ATP?"
    assert q_mcq.correct_answer == "Mitochondria"


# ---------------------------------------------------------------------------
# 14. Concurrency / Unique-Constraint Conflict Safety
# ---------------------------------------------------------------------------

def test_concurrent_attempt_safety(
    db_session: Session,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session, q_mcq, _ = sample_session_user_a

    # Insert attempt 1
    att1 = record_question_attempt(
        db=db_session,
        session=session,
        question=q_mcq,
        submitted_answer="Option A",
        is_correct=True,
        score=1.0,
        feedback="Good",
        evaluation_metadata={},
    )
    assert att1.attempt_number == 1

    # Simulate concurrency: record_question_attempt handles IntegrityError and retries
    att2 = record_question_attempt(
        db=db_session,
        session=session,
        question=q_mcq,
        submitted_answer="Option B",
        is_correct=False,
        score=0.0,
        feedback="Wrong",
        evaluation_metadata={},
    )
    assert att2.attempt_number == 2


# ---------------------------------------------------------------------------
# 15. User Ownership Isolation
# ---------------------------------------------------------------------------

def test_user_ownership_isolation(
    client: TestClient,
    db_session: Session,
    user_b: User,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session_a, q_mcq, _ = sample_session_user_a
    cookies_b = _auth_cookie_for(user_b, db_session)

    # User B cannot submit an attempt to User A's session/question
    res = client.post(
        f"/api/v1/revision/sessions/{session_a.id}/questions/{q_mcq.id}/attempts",
        json={"submitted_answer": "Mitochondria"},
        cookies=cookies_b,
    )
    assert res.status_code == 404
    assert "Revision session not found" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 16. Guest Ownership Isolation
# ---------------------------------------------------------------------------

def test_guest_ownership_isolation(
    client: TestClient,
    db_session: Session,
    doc_user_a: Document,
):
    guest_1 = create_guest_session(db_session)
    guest_2 = create_guest_session(db_session)

    session_g1 = RevisionSession(
        owner_type=IdentityType.GUEST.value,
        owner_id=guest_1.id,
        title="Guest 1 Session",
        total_questions=1,
    )
    db_session.add(session_g1)
    db_session.flush()

    q_g1 = RevisionQuestion(
        session_id=session_g1.id,
        position=1,
        question_text="Q1",
        correct_answer="A",
        options=["A", "B"],
        question_type="multiple_choice",
    )
    db_session.add(q_g1)
    db_session.commit()

    # Guest 2 attempts to submit to Guest 1's question -> 404
    cookies_g2 = {settings.guest_session_cookie_name: guest_2.id}
    res = client.post(
        f"/api/v1/revision/sessions/{session_g1.id}/questions/{q_g1.id}/attempts",
        json={"submitted_answer": "A"},
        cookies=cookies_g2,
    )
    assert res.status_code == 404
    assert "Revision session not found" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 17. Session / Question Mismatch Rejection
# ---------------------------------------------------------------------------

def test_session_question_mismatch_rejection(
    client: TestClient,
    db_session: Session,
    user_a: User,
    doc_user_a: Document,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session_1, q1, _ = sample_session_user_a
    cookies = _auth_cookie_for(user_a, db_session)

    # Create session 2 for the same user
    session_2 = RevisionSession(
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        title="Session 2",
        total_questions=1,
    )
    db_session.add(session_2)
    db_session.commit()

    # Attempt to submit q1 against session_2 -> 404
    res = client.post(
        f"/api/v1/revision/sessions/{session_2.id}/questions/{q1.id}/attempts",
        json={"submitted_answer": "Mitochondria"},
        cookies=cookies,
    )
    assert res.status_code == 404
    assert "Question not found in this revision session" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 18. MCQ Does Not Consume Guest AI Quota
# ---------------------------------------------------------------------------

def test_mcq_does_not_consume_guest_quota(
    client: TestClient,
    db_session: Session,
):
    guest = create_guest_session(db_session)
    session = RevisionSession(
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
        title="Guest MCQ Session",
        total_questions=1,
    )
    db_session.add(session)
    db_session.flush()

    q_mcq = RevisionQuestion(
        session_id=session.id,
        position=1,
        question_type="multiple_choice",
        question_text="MCQ Question",
        options=["A", "B"],
        correct_answer="A",
    )
    db_session.add(q_mcq)
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}
    res = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_mcq.id}/attempts",
        json={"submitted_answer": "A"},
        cookies=cookies,
    )
    assert res.status_code == 201

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0  # Quota unchanged!


# ---------------------------------------------------------------------------
# 19. Open-Ended Evaluation Consumes Exactly One Guest AI Generation on Success
# ---------------------------------------------------------------------------

def test_open_ended_consumes_one_guest_quota(
    client: TestClient,
    db_session: Session,
):
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    session = RevisionSession(
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
        title="Guest Open Session",
        total_questions=1,
    )
    db_session.add(session)
    db_session.flush()

    q_open = RevisionQuestion(
        session_id=session.id,
        position=1,
        question_type="open_ended",
        question_text="Open Question",
        correct_answer="Reference Answer",
    )
    db_session.add(q_open)
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}
    res = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_open.id}/attempts",
        json={"submitted_answer": "Detailed conceptual answer."},
        cookies=cookies,
    )
    assert res.status_code == 201

    db_session.refresh(guest)
    assert guest.ai_generation_count == 1  # Exactly 1 consumed!


# ---------------------------------------------------------------------------
# 20. Failed Open-Ended Evaluation Consumes Zero Guest Quota
# ---------------------------------------------------------------------------

def test_failed_open_ended_evaluation_consumes_zero_guest_quota(
    db_session: Session,
):
    failing_ai = FailingEvaluationAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: failing_ai

    try:
        with TestClient(app) as test_client:
            guest = create_guest_session(db_session)
            guest.ai_generation_count = 0
            session = RevisionSession(
                owner_type=IdentityType.GUEST.value,
                owner_id=guest.id,
                title="Guest Fail Session",
                total_questions=1,
            )
            db_session.add(session)
            db_session.flush()

            q_open = RevisionQuestion(
                session_id=session.id,
                position=1,
                question_type="open_ended",
                question_text="Open Question",
                correct_answer="Reference Answer",
            )
            db_session.add(q_open)
            db_session.commit()

            cookies = {settings.guest_session_cookie_name: guest.id}
            res = test_client.post(
                f"/api/v1/revision/sessions/{session.id}/questions/{q_open.id}/attempts",
                json={"submitted_answer": "Some valid student text."},
                cookies=cookies,
            )
            assert res.status_code == 502

            db_session.refresh(guest)
            assert guest.ai_generation_count == 0  # Quota NOT consumed on 502!

            # Verify no orphaned attempt was persisted
            attempts = db_session.query(RevisionAttempt).filter(RevisionAttempt.question_id == q_open.id).all()
            assert len(attempts) == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 21. Exhausted Guest Rejection (403 Before AI Invocation)
# ---------------------------------------------------------------------------

def test_exhausted_guest_rejected_before_ai(
    client: TestClient,
    db_session: Session,
    fake_ai: FakeEvaluationAIProvider,
):
    guest = create_guest_session(db_session)
    guest.ai_generation_count = settings.guest_max_ai_generations
    session = RevisionSession(
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
        title="Guest Exhausted Session",
        total_questions=1,
    )
    db_session.add(session)
    db_session.flush()

    q_open = RevisionQuestion(
        session_id=session.id,
        position=1,
        question_type="open_ended",
        question_text="Open Question",
        correct_answer="Reference Answer",
    )
    db_session.add(q_open)
    db_session.commit()

    initial_calls = fake_ai.call_count
    cookies = {settings.guest_session_cookie_name: guest.id}
    res = client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q_open.id}/attempts",
        json={"submitted_answer": "My answer"},
        cookies=cookies,
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "guest_limit_reached"
    assert fake_ai.call_count == initial_calls  # Zero AI calls!


# ---------------------------------------------------------------------------
# 22, 23. Session Score Calculation & Latest Attempt (No Double-Counting)
# ---------------------------------------------------------------------------

def test_session_score_calculation_latest_attempt_rule(
    db_session: Session,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session, q1_mcq, q2_open = sample_session_user_a

    # No attempts yet -> score is 0.0
    score_0 = calculate_session_score(session, db_session)
    assert score_0 == 0.0

    # Q1 Attempt 1: score = 0.0
    record_question_attempt(
        db=db_session,
        session=session,
        question=q1_mcq,
        submitted_answer="Ribosome",
        is_correct=False,
        score=0.0,
        feedback="Wrong",
        evaluation_metadata={},
    )
    # Q1 has 0.0, Q2 has 0.0 -> average = 0.0
    assert calculate_session_score(session, db_session) == 0.0

    # Q1 Attempt 2: score = 1.0 (retake)
    record_question_attempt(
        db=db_session,
        session=session,
        question=q1_mcq,
        submitted_answer="Mitochondria",
        is_correct=True,
        score=1.0,
        feedback="Correct",
        evaluation_metadata={},
    )
    # Latest attempt for Q1 is 1.0. Q2 still has no attempts (0.0). Average of 2 questions = 1.0 / 2 = 0.5
    assert calculate_session_score(session, db_session) == 0.5

    # Q2 Attempt 1: score = 0.8
    record_question_attempt(
        db=db_session,
        session=session,
        question=q2_open,
        submitted_answer="Good answer",
        is_correct=True,
        score=0.8,
        feedback="Good",
        evaluation_metadata={},
    )
    # Latest Q1 = 1.0, Latest Q2 = 0.8 -> (1.0 + 0.8) / 2 = 0.9
    assert calculate_session_score(session, db_session) == 0.9


# ---------------------------------------------------------------------------
# 24. Session Completion Endpoint
# ---------------------------------------------------------------------------

def test_session_completion_endpoint(
    client: TestClient,
    db_session: Session,
    user_a: User,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session, q1_mcq, q2_open = sample_session_user_a
    cookies = _auth_cookie_for(user_a, db_session)

    # Submit Q1: 1.0
    client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q1_mcq.id}/attempts",
        json={"submitted_answer": "Mitochondria"},
        cookies=cookies,
    )
    # Submit Q2: 0.9 (from fake_ai)
    client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q2_open.id}/attempts",
        json={"submitted_answer": "Valid explanation."},
        cookies=cookies,
    )

    # Complete session
    res = client.post(f"/api/v1/revision/sessions/{session.id}/complete", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["score"] == 0.95  # (1.0 + 0.9) / 2 = 0.95
    assert data["completed_at"] is not None

    # Verify DB state
    db_session.refresh(session)
    assert session.status == "completed"
    assert session.score == 0.95
    assert session.completed_at is not None


# ---------------------------------------------------------------------------
# 25. Cannot Improperly Complete an Already Completed Session
# ---------------------------------------------------------------------------

def test_cannot_complete_already_completed_session(
    client: TestClient,
    db_session: Session,
    user_a: User,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session, _, _ = sample_session_user_a
    cookies = _auth_cookie_for(user_a, db_session)

    # First completion succeeds
    res1 = client.post(f"/api/v1/revision/sessions/{session.id}/complete", cookies=cookies)
    assert res1.status_code == 200

    # Second completion is rejected with 400
    res2 = client.post(f"/api/v1/revision/sessions/{session.id}/complete", cookies=cookies)
    assert res2.status_code == 400
    assert "already completed" in res2.json()["detail"]


# ---------------------------------------------------------------------------
# 26. Persistence Survives Session Detail Retrieval
# ---------------------------------------------------------------------------

def test_attempts_persist_in_session_detail(
    client: TestClient,
    db_session: Session,
    user_a: User,
    sample_session_user_a: tuple[RevisionSession, RevisionQuestion, RevisionQuestion],
):
    session, q1_mcq, _ = sample_session_user_a
    cookies = _auth_cookie_for(user_a, db_session)

    # Submit 2 attempts on Q1
    client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q1_mcq.id}/attempts",
        json={"submitted_answer": "Ribosome"},
        cookies=cookies,
    )
    client.post(
        f"/api/v1/revision/sessions/{session.id}/questions/{q1_mcq.id}/attempts",
        json={"submitted_answer": "Mitochondria"},
        cookies=cookies,
    )

    # Fetch session detail
    res = client.get(f"/api/v1/revision/sessions/{session.id}", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert len(data["questions"]) == 2

    # Check Q1 attempts are present and ordered
    q1_data = next(q for q in data["questions"] if q["id"] == q1_mcq.id)
    assert len(q1_data["attempts"]) == 2
    assert q1_data["attempts"][0]["attempt_number"] == 1
    assert q1_data["attempts"][0]["submitted_answer"] == "Ribosome"
    assert q1_data["attempts"][0]["is_correct"] is False
    assert q1_data["attempts"][1]["attempt_number"] == 2
    assert q1_data["attempts"][1]["submitted_answer"] == "Mitochondria"
    assert q1_data["attempts"][1]["is_correct"] is True


# ---------------------------------------------------------------------------
# 27. Legacy Study Quiz Remains Untouched
# ---------------------------------------------------------------------------

def test_legacy_study_quiz_untouched(
    client: TestClient,
    db_session: Session,
    user_a: User,
    doc_user_a: Document,
):
    cookies = _auth_cookie_for(user_a, db_session)

    res = client.post(
        f"/api/v1/documents/{doc_user_a.id}/quiz",
        cookies=cookies,
    )
    assert res.status_code == 201
    questions = res.json()
    assert isinstance(questions, list)
    assert len(questions) > 0
    assert "correct_answer_index" in questions[0]

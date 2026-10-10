import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
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
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    User,
)
from app.main import app
from app.schemas.identity import Identity, IdentityType
from app.schemas.revision import RevisionSessionCreateRequest
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_session_service import create_guest_session
from app.services.mastery_service import (
    HALF_LIFE_DAYS,
    LAMBDA_DECAY,
    calculate_mastery_for_attempts,
    calculate_mastery_for_questions,
    get_document_mastery,
    get_overall_mastery,
)
from app.services.revision_service import UnsupportedTopicError, clean_and_normalize_topic
from app.services.user_session_service import create_user_session


# ---------------------------------------------------------------------------
# Test Providers & Helpers
# ---------------------------------------------------------------------------

class MockMasteryAIProvider(AIProvider):
    def __init__(self, response_text: Optional[str] = None) -> None:
        self.response_text = response_text
        self.last_prompt: Optional[str] = None
        self.calls = 0

    async def generate_text(self, prompt: str) -> str:
        self.calls += 1
        self.last_prompt = prompt
        if self.response_text is not None:
            return self.response_text
        return json.dumps([
            {
                "question_text": "What is the primary function of mitochondria?",
                "question_type": "multiple_choice",
                "options": ["ATP generation", "Protein synthesis", "Lipid storage", "DNA replication"],
                "correct_answer": "ATP generation",
                "explanation": "Mitochondria produce cellular ATP via oxidative phosphorylation.",
                "source_document_id": "test-doc",
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
                "topic": "Cellular Respiration",
            }
        ])


def _auth_cookie_for_user(user: User, db: Session) -> dict[str, str]:
    session = create_user_session(db, user.id)
    return {settings.user_session_cookie_name: session.id}


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
def mock_ai():
    return MockMasteryAIProvider()


@pytest.fixture()
def test_client(mock_ai):
    app.dependency_overrides[get_ai_provider] = lambda: mock_ai
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-mastery-{uid}",
        email=f"user-mastery-{uid}@example.com",
        password_hash="hashed_pw",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def other_user(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"other-user-{uid}",
        email=f"other-{uid}@example.com",
        password_hash="hashed_pw",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def test_document(db_session: Session, test_user: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-bio-{uid}",
        original_filename="biology_101.pdf",
        stored_filename=f"bio_{uid}.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration. Photosynthesis converts sunlight into chemical energy.",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# 1. Topic Normalization & Schema Validation Tests
# ---------------------------------------------------------------------------

def test_clean_and_normalize_topic():
    # Valid normalizations
    assert clean_and_normalize_topic("Photosynthesis") == ("Photosynthesis", "photosynthesis")
    assert clean_and_normalize_topic("  Cellular   Respiration  ") == ("Cellular Respiration", "cellular respiration")
    assert clean_and_normalize_topic('"Krebs Cycle"') == ("Krebs Cycle", "krebs cycle")
    assert clean_and_normalize_topic("NFKC ｐｈｏｔｏｓｙｎｔｈｅｓｉｓ") == ("NFKC photosynthesis", "nfkc photosynthesis")

    # Generic placeholders filtered out
    assert clean_and_normalize_topic("general") is None
    assert clean_and_normalize_topic("General") is None
    assert clean_and_normalize_topic("N/A") is None
    assert clean_and_normalize_topic("none") is None
    assert clean_and_normalize_topic("overview") is None
    assert clean_and_normalize_topic("topic") is None
    assert clean_and_normalize_topic("document") is None

    # Control characters rejected
    assert clean_and_normalize_topic("Photo\nsynthesis") is None
    assert clean_and_normalize_topic("Photo\tsynthesis") is None
    assert clean_and_normalize_topic("Cell\x00Division") is None

    # Length constraints
    assert clean_and_normalize_topic("a") is None
    assert clean_and_normalize_topic("a" * 101) is None
    assert clean_and_normalize_topic("") is None
    assert clean_and_normalize_topic(None) is None


def test_topic_focus_schema_validation():
    # Valid topic focus
    req = RevisionSessionCreateRequest(document_ids=["doc-1"], topic_focus="Photosynthesis")
    assert req.topic_focus == "Photosynthesis"

    # Whitespace cleanup
    req_ws = RevisionSessionCreateRequest(document_ids=["doc-1"], topic_focus="  Cellular   Respiration  ")
    assert req_ws.topic_focus == "Cellular Respiration"

    # Fullwidth Unicode normalized
    req_unicode = RevisionSessionCreateRequest(document_ids=["doc-1"], topic_focus="ｐｈｏｔｏｓｙｎｔｈｅｓｉｓ")
    assert req_unicode.topic_focus == "photosynthesis"

    # Control characters rejected
    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], topic_focus="Photo\nsynthesis")

    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], topic_focus="Cell\x00Division")

    # Length bounds (< 2 or > 100)
    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], topic_focus="x")

    with pytest.raises(ValidationError):
        RevisionSessionCreateRequest(document_ids=["doc-1"], topic_focus="a" * 101)


# ---------------------------------------------------------------------------
# 2. Mastery Mathematical Decay Tests
# ---------------------------------------------------------------------------

def test_mastery_math_half_life_decay():
    now = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    
    # Verify half-life constants
    assert HALF_LIFE_DAYS == 14.0
    assert math.isclose(LAMBDA_DECAY, math.log(2) / 14.0, rel_tol=1e-9)

    # 1. Delta t = 0 days -> weight = 1.0
    attempts_0d = [(1.0, now)]
    res_0d = calculate_mastery_for_attempts(attempts_0d, now=now)
    assert res_0d.score == 1.0

    # 2. Delta t = 14 days -> weight = 0.5
    # Two attempts: Attempt 1 at t=0 (score 1.0, w=1.0), Attempt 2 at t=14d (score 0.0, w=0.5)
    # Expected weighted score: (1.0*1.0 + 0.0*0.5) / (1.0 + 0.5) = 1.0 / 1.5 = 0.6667
    attempts_combo = [
        (1.0, now),
        (0.0, now - timedelta(days=14)),
    ]
    res_combo = calculate_mastery_for_attempts(attempts_combo, now=now)
    assert math.isclose(res_combo.score, round(1.0 / 1.5, 4), abs_tol=1e-4)

    # 3. Delta t = 28 days -> weight = 0.25
    # Attempt 1 at t=0 (score 0.0, w=1.0), Attempt 2 at t=28d (score 1.0, w=0.25)
    # Expected weighted score: (0.0*1.0 + 1.0*0.25) / (1.0 + 0.25) = 0.25 / 1.25 = 0.2
    attempts_28d = [
        (0.0, now),
        (1.0, now - timedelta(days=28)),
    ]
    res_28d = calculate_mastery_for_attempts(attempts_28d, now=now)
    assert res_28d.score == 0.2


# ---------------------------------------------------------------------------
# 3. Mastery Eligibility Gate & Tiers Tests
# ---------------------------------------------------------------------------

def test_mastery_eligibility_and_tiers():
    now = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)

    # 0 questions -> unassessed, score 0.0
    res_0 = calculate_mastery_for_attempts([], now=now)
    assert res_0.tier == "unassessed"
    assert res_0.is_assessed is False
    assert res_0.attempted_count == 0
    assert res_0.questions_needed == 3
    assert res_0.score == 0.0
    assert res_0.last_attempted_at is None

    # 1 question -> unassessed, questions_needed = 2
    res_1 = calculate_mastery_for_attempts([(1.0, now)], now=now)
    assert res_1.tier == "unassessed"
    assert res_1.is_assessed is False
    assert res_1.attempted_count == 1
    assert res_1.questions_needed == 2
    assert res_1.score == 1.0
    assert res_1.last_attempted_at == now

    # 2 questions -> unassessed, questions_needed = 1
    res_2 = calculate_mastery_for_attempts([(1.0, now), (1.0, now)], now=now)
    assert res_2.tier == "unassessed"
    assert res_2.is_assessed is False
    assert res_2.attempted_count == 2
    assert res_2.questions_needed == 1
    assert res_2.score == 1.0

    # 3 questions >= 0.85 -> mastered
    res_3_high = calculate_mastery_for_attempts([(1.0, now), (0.9, now), (0.85, now)], now=now)
    assert res_3_high.tier == "mastered"
    assert res_3_high.is_assessed is True
    assert res_3_high.attempted_count == 3
    assert res_3_high.questions_needed == 0
    assert res_3_high.score >= 0.85

    # Exactly 0.85 -> mastered
    res_exact_85 = calculate_mastery_for_attempts([(0.85, now), (0.85, now), (0.85, now)], now=now)
    assert res_exact_85.tier == "mastered"

    # 0.8499 -> proficient
    res_prof = calculate_mastery_for_attempts([(0.80, now), (0.75, now), (0.70, now)], now=now)
    assert res_prof.tier == "proficient"
    assert res_prof.is_assessed is True
    assert 0.60 <= res_prof.score < 0.85

    # Exactly 0.60 -> proficient
    res_exact_60 = calculate_mastery_for_attempts([(0.60, now), (0.60, now), (0.60, now)], now=now)
    assert res_exact_60.tier == "proficient"

    # < 0.60 -> needs_practice
    res_low = calculate_mastery_for_attempts([(0.50, now), (0.40, now), (0.30, now)], now=now)
    assert res_low.tier == "needs_practice"
    assert res_low.is_assessed is True
    assert res_low.score < 0.60


# ---------------------------------------------------------------------------
# 4. Latest Attempt Selection & Unattempted Exclusion
# ---------------------------------------------------------------------------

def test_calculate_mastery_for_questions_latest_attempt(db_session: Session, test_user: User):
    now = datetime.now(timezone.utc)
    session = RevisionSession(
        id=f"sess-{uuid.uuid4().hex[:8]}",
        title="Test Session",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="completed",
    )
    db_session.add(session)
    db_session.commit()

    # Question 1: 2 attempts, attempt 1 = 0.2, attempt 2 = 1.0 (should use 1.0)
    q1 = RevisionQuestion(
        id=f"q1-{uuid.uuid4().hex[:8]}",
        session_id=session.id,
        position=1,
        question_text="Q1",
        correct_answer="A",
    )
    db_session.add(q1)
    db_session.flush()

    att1_1 = RevisionAttempt(
        session_id=session.id,
        question_id=q1.id,
        attempt_number=1,
        submitted_answer="Wrong",
        score=0.2,
        is_correct=False,
        created_at=now - timedelta(hours=2),
    )
    att1_2 = RevisionAttempt(
        session_id=session.id,
        question_id=q1.id,
        attempt_number=2,
        submitted_answer="Right",
        score=1.0,
        is_correct=True,
        created_at=now,
    )
    db_session.add_all([att1_1, att1_2])

    # Question 2: 1 attempt = 0.9
    q2 = RevisionQuestion(
        id=f"q2-{uuid.uuid4().hex[:8]}",
        session_id=session.id,
        position=2,
        question_text="Q2",
        correct_answer="B",
    )
    db_session.add(q2)
    db_session.flush()
    att2 = RevisionAttempt(
        session_id=session.id,
        question_id=q2.id,
        attempt_number=1,
        submitted_answer="Right",
        score=0.9,
        is_correct=True,
        created_at=now,
    )
    db_session.add(att2)

    # Question 3: 1 attempt = 0.8
    q3 = RevisionQuestion(
        id=f"q3-{uuid.uuid4().hex[:8]}",
        session_id=session.id,
        position=3,
        question_text="Q3",
        correct_answer="C",
    )
    db_session.add(q3)
    db_session.flush()
    att3 = RevisionAttempt(
        session_id=session.id,
        question_id=q3.id,
        attempt_number=1,
        submitted_answer="Right",
        score=0.8,
        is_correct=True,
        created_at=now,
    )
    db_session.add(att3)

    # Question 4: 0 attempts (unanswered) - must be excluded from mastery evidence
    q4 = RevisionQuestion(
        id=f"q4-{uuid.uuid4().hex[:8]}",
        session_id=session.id,
        position=4,
        question_text="Q4",
        correct_answer="D",
    )
    db_session.add(q4)
    db_session.commit()

    # Re-fetch questions with attempts
    questions = db_session.query(RevisionQuestion).filter(RevisionQuestion.session_id == session.id).all()
    result = calculate_mastery_for_questions(questions, now=now)

    assert result.attempted_count == 3
    assert result.is_assessed is True
    # Weighted average of 1.0, 0.9, 0.8 at t=0 -> 0.90
    assert math.isclose(result.score, 0.90, abs_tol=1e-2)
    assert result.tier == "mastered"


# ---------------------------------------------------------------------------
# 5. Overall Mastery Aggregation & Completed Sessions Only
# ---------------------------------------------------------------------------

def test_overall_mastery_ignores_in_progress_and_foreign_sessions(
    db_session: Session,
    test_user: User,
    other_user: User,
    test_document: Document,
):
    now = datetime.now(timezone.utc)
    user_identity = Identity(type=IdentityType.USER, id=test_user.id)
    other_identity = Identity(type=IdentityType.USER, id=other_user.id)

    # 1. Completed session for test_user with 3 questions
    s1 = RevisionSession(
        id=f"s1-{uuid.uuid4().hex[:8]}",
        title="Completed User Session",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="completed",
        completed_at=now,
    )
    db_session.add(s1)
    db_session.flush()

    for idx, sc in enumerate([1.0, 0.9, 0.8], start=1):
        q = RevisionQuestion(
            id=f"q-s1-{idx}-{uuid.uuid4().hex[:8]}",
            session_id=s1.id,
            position=idx,
            question_text=f"Question {idx}",
            correct_answer="A",
            source_document_id=test_document.id,
            evidence_metadata={
                "source_document_id": test_document.id,
                "document_title": test_document.original_filename,
                "topic": "Bioenergetics",
                "topic_key": "bioenergetics",
            },
        )
        db_session.add(q)
        db_session.flush()
        att = RevisionAttempt(
            session_id=s1.id,
            question_id=q.id,
            attempt_number=1,
            submitted_answer="A",
            score=sc,
            is_correct=True,
            created_at=now,
        )
        db_session.add(att)

    # 2. In-progress session for test_user with poor scores (must be ignored)
    s2_in_prog = RevisionSession(
        id=f"s2-{uuid.uuid4().hex[:8]}",
        title="In-Progress User Session",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="in_progress",
    )
    db_session.add(s2_in_prog)
    db_session.flush()

    q_prog = RevisionQuestion(
        id=f"q-prog-{uuid.uuid4().hex[:8]}",
        session_id=s2_in_prog.id,
        position=1,
        question_text="In prog question",
        correct_answer="A",
        source_document_id=test_document.id,
        evidence_metadata={"topic": "Bioenergetics", "topic_key": "bioenergetics"},
    )
    db_session.add(q_prog)
    db_session.flush()
    att_prog = RevisionAttempt(
        session_id=s2_in_prog.id,
        question_id=q_prog.id,
        attempt_number=1,
        submitted_answer="Wrong",
        score=0.0,
        is_correct=False,
        created_at=now,
    )
    db_session.add(att_prog)

    # 3. Completed session for other_user (must be ignored for test_user)
    s3_other = RevisionSession(
        id=f"s3-{uuid.uuid4().hex[:8]}",
        title="Other User Session",
        owner_type=IdentityType.USER.value,
        owner_id=other_user.id,
        status="completed",
        completed_at=now,
    )
    db_session.add(s3_other)
    db_session.commit()

    # Query mastery for test_user
    summary_user = get_overall_mastery(db_session, user_identity, now=now)
    assert summary_user.total_completed_sessions == 1
    assert summary_user.total_attempted_questions == 3
    assert summary_user.total_attempts == 3
    # Unweighted average of 1.0, 0.9, 0.8 is 0.90
    assert math.isclose(summary_user.overall_attempt_accuracy, 0.90, abs_tol=1e-3)
    assert len(summary_user.document_masteries) == 1
    assert summary_user.document_masteries[0].mastery.tier == "mastered"
    assert len(summary_user.topic_masteries) == 1
    assert summary_user.topic_masteries[0].topic_display == "Bioenergetics"
    assert summary_user.topic_masteries[0].mastery.tier == "mastered"

    # Query mastery for other_user -> empty
    summary_other = get_overall_mastery(db_session, other_identity, now=now)
    assert summary_other.total_completed_sessions == 1
    assert summary_other.total_attempted_questions == 0
    assert summary_other.overall_attempt_accuracy == 0.0
    assert len(summary_other.document_masteries) == 0


# ---------------------------------------------------------------------------
# 6. Topic Grouping & Display Label Preservation
# ---------------------------------------------------------------------------

def test_topic_grouping_and_display_label_preservation(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    now = datetime.now(timezone.utc)
    identity = Identity(type=IdentityType.USER, id=test_user.id)

    s = RevisionSession(
        id=f"sess-topic-{uuid.uuid4().hex[:8]}",
        title="Topic Grouping Session",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="completed",
        completed_at=now,
    )
    db_session.add(s)
    db_session.flush()

    # Question 1: topic "krebs cycle", created earlier
    q1 = RevisionQuestion(
        id=f"q1-top-{uuid.uuid4().hex[:8]}",
        session_id=s.id,
        position=1,
        question_text="Q1",
        correct_answer="A",
        source_document_id=test_document.id,
        evidence_metadata={
            "source_document_id": test_document.id,
            "document_title": test_document.original_filename,
            "topic": "krebs cycle",
            "topic_key": "krebs cycle",
        },
    )
    # Question 2: topic "Krebs Cycle", created later with better casing
    q2 = RevisionQuestion(
        id=f"q2-top-{uuid.uuid4().hex[:8]}",
        session_id=s.id,
        position=2,
        question_text="Q2",
        correct_answer="B",
        source_document_id=test_document.id,
        evidence_metadata={
            "source_document_id": test_document.id,
            "document_title": test_document.original_filename,
            "topic": "Krebs Cycle",
            "topic_key": "krebs cycle",
        },
    )
    # Question 3: topic "KREBS CYCLE", latest attempt
    q3 = RevisionQuestion(
        id=f"q3-top-{uuid.uuid4().hex[:8]}",
        session_id=s.id,
        position=3,
        question_text="Q3",
        correct_answer="C",
        source_document_id=test_document.id,
        evidence_metadata={
            "source_document_id": test_document.id,
            "document_title": test_document.original_filename,
            "topic": "Krebs Cycle (TCA)",
            "topic_key": "krebs cycle",
        },
    )
    # Question 4: generic placeholder "General" -> filtered out from topics
    q4 = RevisionQuestion(
        id=f"q4-top-{uuid.uuid4().hex[:8]}",
        session_id=s.id,
        position=4,
        question_text="Q4",
        correct_answer="D",
        source_document_id=test_document.id,
        evidence_metadata={
            "source_document_id": test_document.id,
            "document_title": test_document.original_filename,
            "topic": "General",
        },
    )
    # Question 5: legacy question without topic metadata
    q5 = RevisionQuestion(
        id=f"q5-legacy-{uuid.uuid4().hex[:8]}",
        session_id=s.id,
        position=5,
        question_text="Q5",
        correct_answer="E",
        source_document_id=test_document.id,
        evidence_metadata={
            "source_document_id": test_document.id,
            "document_title": test_document.original_filename,
        },
    )
    db_session.add_all([q1, q2, q3, q4, q5])
    db_session.flush()

    # Add attempts with timestamps
    att1 = RevisionAttempt(
        session_id=s.id,
        question_id=q1.id,
        attempt_number=1,
        submitted_answer="A",
        score=1.0,
        is_correct=True,
        created_at=now - timedelta(minutes=10),
    )
    att2 = RevisionAttempt(
        session_id=s.id,
        question_id=q2.id,
        attempt_number=1,
        submitted_answer="B",
        score=0.9,
        is_correct=True,
        created_at=now - timedelta(minutes=5),
    )
    att3 = RevisionAttempt(
        session_id=s.id,
        question_id=q3.id,
        attempt_number=1,
        submitted_answer="C",
        score=0.85,
        is_correct=True,
        created_at=now,
    )
    att4 = RevisionAttempt(
        session_id=s.id,
        question_id=q4.id,
        attempt_number=1,
        submitted_answer="D",
        score=1.0,
        is_correct=True,
        created_at=now,
    )
    att5 = RevisionAttempt(
        session_id=s.id,
        question_id=q5.id,
        attempt_number=1,
        submitted_answer="E",
        score=1.0,
        is_correct=True,
        created_at=now,
    )
    db_session.add_all([att1, att2, att3, att4, att5])
    db_session.commit()

    summary = get_overall_mastery(db_session, identity, now=now)
    
    # Document mastery aggregates all 5 questions
    assert len(summary.document_masteries) == 1
    doc_m = summary.document_masteries[0]
    assert doc_m.mastery.attempted_count == 5
    assert doc_m.mastery.is_assessed is True
    assert doc_m.mastery.tier == "mastered"

    # Topic masteries has only 1 topic group ("krebs cycle")
    # because q4 ("General") and q5 (no topic) were excluded from topic groups
    assert len(summary.topic_masteries) == 1
    top_m = summary.topic_masteries[0]
    assert top_m.topic_key == "krebs cycle"
    # Display label from the latest attempt on q3
    assert top_m.topic_display == "Krebs Cycle (TCA)"
    assert top_m.mastery.attempted_count == 3
    assert top_m.mastery.is_assessed is True
    assert top_m.mastery.tier == "mastered"


# ---------------------------------------------------------------------------
# 7. Archived Document Provenance & Sorting
# ---------------------------------------------------------------------------

def test_archived_document_provenance_and_sorting(
    db_session: Session,
    test_user: User,
):
    now = datetime.now(timezone.utc)
    identity = Identity(type=IdentityType.USER, id=test_user.id)

    # Create active document "Zebra Study"
    active_doc = Document(
        id=f"doc-zebra-{uuid.uuid4().hex[:8]}",
        original_filename="zebra_study.pdf",
        stored_filename="z.pdf",
        status="ready",
        extracted_text="Zebra stripes provide camouflage.",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
    )
    db_session.add(active_doc)
    db_session.commit()

    # Create completed session referencing active_doc
    s_active = RevisionSession(
        id=f"sess-act-{uuid.uuid4().hex[:8]}",
        title="Active Doc Session",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="completed",
        completed_at=now,
    )
    db_session.add(s_active)
    db_session.flush()

    for i in range(3):
        q = RevisionQuestion(
            id=f"q-act-{i}-{uuid.uuid4().hex[:8]}",
            session_id=s_active.id,
            position=i + 1,
            question_text=f"Zebra Q{i}",
            correct_answer="A",
            source_document_id=active_doc.id,
            evidence_metadata={
                "source_document_id": active_doc.id,
                "document_title": active_doc.original_filename,
            },
        )
        db_session.add(q)
        db_session.flush()
        db_session.add(RevisionAttempt(
            session_id=s_active.id,
            question_id=q.id,
            attempt_number=1,
            submitted_answer="A",
            score=1.0,
            is_correct=True,
            created_at=now,
        ))

    # Create completed session referencing a DELETED document "Apple History" (alphabetically earlier than Zebra)
    deleted_doc_id = f"doc-deleted-{uuid.uuid4().hex[:8]}"
    s_archived = RevisionSession(
        id=f"sess-arc-{uuid.uuid4().hex[:8]}",
        title="Archived Doc Session",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="completed",
        completed_at=now,
    )
    db_session.add(s_archived)
    db_session.flush()

    for i in range(3):
        q = RevisionQuestion(
            id=f"q-arc-{i}-{uuid.uuid4().hex[:8]}",
            session_id=s_archived.id,
            position=i + 1,
            question_text=f"Apple Q{i}",
            correct_answer="B",
            source_document_id=deleted_doc_id,
            evidence_metadata={
                "source_document_id": deleted_doc_id,
                "document_title": "apple_history.pdf",
            },
        )
        db_session.add(q)
        db_session.flush()
        db_session.add(RevisionAttempt(
            session_id=s_archived.id,
            question_id=q.id,
            attempt_number=1,
            submitted_answer="B",
            score=0.9,
            is_correct=True,
            created_at=now,
        ))

    db_session.commit()

    summary = get_overall_mastery(db_session, identity, now=now)
    assert len(summary.document_masteries) == 2

    # Verify sorting: Active document first (zebra_study.pdf), then archived document (apple_history.pdf)
    first_doc = summary.document_masteries[0]
    second_doc = summary.document_masteries[1]

    assert first_doc.is_archived is False
    assert first_doc.document_id == active_doc.id
    assert first_doc.document_title == "zebra_study.pdf"

    assert second_doc.is_archived is True
    assert second_doc.document_id == deleted_doc_id
    assert second_doc.document_title == "apple_history.pdf"

    # get_document_mastery lookup
    doc_m = get_document_mastery(db_session, identity, deleted_doc_id, now=now)
    assert doc_m is not None
    assert doc_m.is_archived is True
    assert doc_m.document_title == "apple_history.pdf"


# ---------------------------------------------------------------------------
# 8. API Integration: Targeted Revision & Quota Safety
# ---------------------------------------------------------------------------

def test_verify_evidence_in_document():
    from app.services.revision_service import verify_evidence_in_document
    doc_text = "Mitochondria generate cellular ATP via aerobic respiration. Photosynthesis converts sunlight into chemical energy."

    # Exact match
    assert verify_evidence_in_document("Photosynthesis converts sunlight into chemical energy.", doc_text) is True

    # Whitespace and newlines normalization
    assert verify_evidence_in_document("Photosynthesis   converts\n  sunlight into chemical energy.", doc_text) is True

    # Quoted string
    assert verify_evidence_in_document('"Photosynthesis converts sunlight into chemical energy."', doc_text) is True
    assert verify_evidence_in_document("“Photosynthesis converts sunlight into chemical energy.”", doc_text) is True

    # Substring clause
    assert verify_evidence_in_document("cellular ATP via aerobic respiration", doc_text) is True

    # Fabricated content
    assert verify_evidence_in_document("Mitochondria generate nuclear fission energy.", doc_text) is False
    assert verify_evidence_in_document("Aliens built the pyramids.", doc_text) is False

    # Empty, None, or too short
    assert verify_evidence_in_document("", doc_text) is False
    assert verify_evidence_in_document(None, doc_text) is False
    assert verify_evidence_in_document("ATP", doc_text) is False


def test_api_targeted_revision_with_topic_focus(
    test_client: TestClient,
    db_session: Session,
    test_user: User,
    test_document: Document,
    mock_ai: MockMasteryAIProvider,
):
    cookies = _auth_cookie_for_user(test_user, db_session)
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Photosynthesis",
        "questions": [
            {
                "question_text": "How do light-dependent reactions produce ATP?",
                "question_type": "multiple_choice",
                "options": ["Photophosphorylation", "Fermentation", "Glycolysis", "Krebs Cycle"],
                "correct_answer": "Photophosphorylation",
                "explanation": "Light energy drives ATP synthesis.",
                "source_document_id": test_document.id,
                "evidence_snippet": "Photosynthesis converts sunlight into chemical energy.",
                "subtopic": "Light Reactions",
            }
        ],
    })

    payload = {
        "document_ids": [test_document.id],
        "topic_focus": "Photosynthesis",
        "question_count": 1,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201
    data = res.json()

    # Verify session config has topic_focus
    sess_id = data["id"]
    sess_db = db_session.query(RevisionSession).filter(RevisionSession.id == sess_id).one()
    assert sess_db.config.get("topic_focus") == "Photosynthesis"

    # Verify question attribution: primary topic matches topic_focus, subtopic captures "Light Reactions"
    q_db = db_session.query(RevisionQuestion).filter(RevisionQuestion.session_id == sess_id).one()
    meta = q_db.evidence_metadata or {}
    assert meta.get("topic") == "Photosynthesis"
    assert meta.get("topic_key") == "photosynthesis"
    assert meta.get("subtopic") == "Light Reactions"


def test_api_unsupported_topic_returns_422_and_consumes_no_quota(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-{uuid.uuid4().hex[:8]}",
        original_filename="intro_mechanics.pdf",
        stored_filename="m.pdf",
        status="ready",
        extracted_text="Newton's laws of motion explain classical kinematics.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    # AI returns empty list or unsupported indication because topic is not supported in excerpt
    mock_ai.response_text = json.dumps([])

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Organic Chemistry",
        "question_count": 2,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 422
    assert "not contain sufficient content" in res.json()["detail"]

    # Verify guest quota was NOT consumed
    db_session.refresh(guest)
    assert guest.ai_generation_count == 0

    # Verify no session was persisted
    count_sessions = db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count()
    assert count_sessions == 0


def test_api_non_empty_unsupported_topic_returns_422_and_consumes_no_quota(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a response with questions that explicitly flags topic_supported: false
    (or unsupported: true) is rejected with HTTP 422 and does NOT persist a session or consume quota.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-unsupp-{uuid.uuid4().hex[:8]}",
        original_filename="intro_mechanics.pdf",
        stored_filename="m2.pdf",
        status="ready",
        extracted_text="Newton's laws of motion explain classical kinematics.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    # Non-empty questions but explicitly unsupported
    mock_ai.response_text = json.dumps({
        "topic_supported": False,
        "reason": "Excerpts do not cover Quantum Electrodynamics.",
        "questions": [
            {
                "question_text": "What is Coulomb's law?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Newton's laws of motion explain classical kinematics.",
            }
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Quantum Electrodynamics",
        "question_count": 1,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 422
    assert "not contain sufficient content" in res.json()["detail"]

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0

    count_sessions = db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count()
    assert count_sessions == 0


def test_api_targeted_invalid_source_document_id_fails_safely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that targeted questions citing an invalid source document ID are not
    silently attributed to the first document, and fail safely with 502 consuming 0 quota.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-valid-{uuid.uuid4().hex[:8]}",
        original_filename="notes.pdf",
        stored_filename="notes.pdf",
        status="ready",
        extracted_text="Photosynthesis converts sunlight into chemical energy.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    # Model cites a fabricated document ID that was not provided
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Photosynthesis",
        "questions": [
            {
                "question_text": "Explain light reactions.",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": "fabricated-external-doc-id-999",
                "evidence_snippet": "Photosynthesis converts sunlight into chemical energy.",
            }
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Photosynthesis",
        "question_count": 1,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0

    count_sessions = db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count()
    assert count_sessions == 0


def test_api_targeted_missing_or_fabricated_evidence_fails_safely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that missing or fabricated evidence in targeted questions is rejected
    without substituting an arbitrary excerpt, failing safely with 502 and consuming 0 quota.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-ev-{uuid.uuid4().hex[:8]}",
        original_filename="biology.pdf",
        stored_filename="b.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}

    # Case A: Missing evidence snippet
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "What do mitochondria produce?",
                "question_type": "multiple_choice",
                "options": ["ATP", "Lipids", "Sugars", "DNA"],
                "correct_answer": "ATP",
                "source_document_id": doc.id,
                "evidence_snippet": "",  # missing evidence snippet
            }
        ],
    })

    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 1,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0

    # Case B: Fabricated evidence snippet (not in document text)
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "What do mitochondria produce?",
                "question_type": "multiple_choice",
                "options": ["ATP", "Lipids", "Sugars", "DNA"],
                "correct_answer": "ATP",
                "source_document_id": doc.id,
                "evidence_snippet": "Martians established cellular factories to produce exotic matter.",
            }
        ],
    })

    res2 = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res2.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_malformed_structures_fail_safely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that malformed structures (bare list, missing topic_supported, contradictory empty list)
    fail safely with HTTP 502 and consume 0 quota.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-struct-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 1,
    }

    # Structure 1: Bare list of questions without topic_supported wrapper
    mock_ai.response_text = json.dumps([
        {
            "question_text": "What do mitochondria produce?",
            "question_type": "multiple_choice",
            "options": ["ATP", "Lipids", "Sugars", "DNA"],
            "correct_answer": "ATP",
            "source_document_id": doc.id,
            "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
        }
    ])
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    # Structure 2: Dict missing topic_supported confirmation
    mock_ai.response_text = json.dumps({
        "questions": [
            {
                "question_text": "What do mitochondria produce?",
                "question_type": "multiple_choice",
                "options": ["ATP", "Lipids", "Sugars", "DNA"],
                "correct_answer": "ATP",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            }
        ]
    })
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    # Structure 3: Contradictory topic_supported: true but empty questions array
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "questions": [],
    })
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_ordinary_revision_generation_intact(
    test_client: TestClient,
    db_session: Session,
    test_user: User,
    test_document: Document,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that ordinary revision generation (without topic_focus) preserves existing behavior:
    - Accepts standard JSON array format
    - Gracefully falls back to first document if source_document_id missing
    - Gracefully falls back to excerpt if evidence_snippet missing
    """
    cookies = _auth_cookie_for_user(test_user, db_session)
    mock_ai.response_text = json.dumps([
        {
            "question_text": "What do cells use ATP for?",
            "question_type": "multiple_choice",
            "options": ["Energy transfer", "Insulation", "Storage", "Filtration"],
            "correct_answer": "Energy transfer",
            "explanation": "ATP provides energy for biochemical work.",
            "source_document_id": "unrecognized-legacy-id",  # falls back to test_document.id
            "evidence_snippet": "",  # falls back to excerpt in ordinary mode
            "topic": "Cell Biology",
        }
    ])

    payload = {
        "document_ids": [test_document.id],
        "question_count": 1,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201
    data = res.json()
    assert len(data["questions"]) == 1
    q = data["questions"][0]
    assert q["source_document_id"] == test_document.id
    assert q["evidence_snippet"] is not None
    assert len(q["evidence_snippet"]) > 0


def test_api_ai_failure_returns_502_and_consumes_no_quota(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-fail-{uuid.uuid4().hex[:8]}",
        original_filename="doc.pdf",
        stored_filename="d.pdf",
        status="ready",
        extracted_text="Some text.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    class FailingProvider(AIProvider):
        async def generate_text(self, prompt: str) -> str:
            raise AIProviderError("Upstream model connection failure")

    app.dependency_overrides[get_ai_provider] = lambda: FailingProvider()
    try:
        cookies = {settings.guest_session_cookie_name: guest.id}
        payload = {
            "document_ids": [doc.id],
            "question_count": 2,
        }
        res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
        assert res.status_code == 502

        # Verify guest quota was NOT consumed
        db_session.refresh(guest)
        assert guest.ai_generation_count == 0

        # Verify no session was persisted
        count_sessions = db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count()
        assert count_sessions == 0
    finally:
        app.dependency_overrides.clear()


def test_api_targeted_complete_valid_response_exact_count(
    test_client: TestClient,
    db_session: Session,
    test_user: User,
    test_document: Document,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a complete valid targeted response succeeds and persists exactly
    the requested number of questions.
    """
    cookies = _auth_cookie_for_user(test_user, db_session)
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Photosynthesis",
        "questions": [
            {
                "question_text": "What do light reactions produce?",
                "question_type": "multiple_choice",
                "options": ["ATP", "Lipids", "Sugars", "DNA"],
                "correct_answer": "ATP",
                "explanation": "Light reactions generate ATP.",
                "source_document_id": test_document.id,
                "evidence_snippet": "Photosynthesis converts sunlight into chemical energy.",
                "subtopic": "Light Reactions",
            },
            {
                "question_text": "What energy source drives photosynthesis?",
                "question_type": "multiple_choice",
                "options": ["Sunlight", "Geothermal", "Wind", "Combustion"],
                "correct_answer": "Sunlight",
                "explanation": "Sunlight drives the photosynthetic reactions.",
                "source_document_id": test_document.id,
                "evidence_snippet": "Photosynthesis converts sunlight into chemical energy.",
                "subtopic": "Solar Energy",
            },
        ],
    })

    payload = {
        "document_ids": [test_document.id],
        "topic_focus": "Photosynthesis",
        "question_count": 2,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201
    data = res.json()
    assert len(data["questions"]) == 2
    sess_db = db_session.query(RevisionSession).filter(RevisionSession.id == data["id"]).one()
    assert sess_db.total_questions == 2


def test_api_targeted_mixed_invalid_source_doc_id_fails_entirely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a mixed response with 1 valid question and 1 question with an invalid
    source document ID fails entirely with HTTP 502, consumes 0 quota, and persists no session.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-mix1-{uuid.uuid4().hex[:8]}",
        original_filename="notes.pdf",
        stored_filename="notes.pdf",
        status="ready",
        extracted_text="Photosynthesis converts sunlight into chemical energy.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Photosynthesis",
        "questions": [
            {
                "question_text": "Valid Q1?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Photosynthesis converts sunlight into chemical energy.",
            },
            {
                "question_text": "Invalid doc Q2?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": "unrecognized-external-doc-id",
                "evidence_snippet": "Photosynthesis converts sunlight into chemical energy.",
            },
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Photosynthesis",
        "question_count": 2,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_mixed_missing_or_fabricated_evidence_fails_entirely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a mixed response with 1 valid question and 1 question with missing or
    fabricated evidence fails entirely with HTTP 502, consumes 0 quota, and persists no session.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-mix2-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 2,
    }

    # Case A: Q1 valid, Q2 missing evidence snippet
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Valid Q1?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Missing evidence Q2?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "",
            },
        ],
    })
    res_a = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res_a.status_code == 502
    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0

    # Case B: Q1 valid, Q2 fabricated evidence
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Valid Q1?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Fabricated evidence Q2?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Extraterrestrial energy sources replace normal metabolism.",
            },
        ],
    })
    res_b = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res_b.status_code == 502
    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_mixed_malformed_question_fails_entirely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a mixed response with 1 valid question and 1 malformed question (e.g. empty text
    or missing options) fails entirely with HTTP 502, consumes 0 quota, and persists no session.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-mix3-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Valid Q1?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "",  # malformed empty question text
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 2,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_fewer_questions_than_requested_fails_entirely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a targeted response providing fewer grounded questions than requested
    fails entirely with HTTP 502, consumes 0 quota, and persists no session.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-few-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    # Requested 3 questions, but AI returned only 2 questions
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Valid Q1?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Valid Q2?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 3,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_mixed_mcq_missing_options_fails_entirely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a targeted revision request with mixed question type where an MCQ item
    is missing options fails entirely with HTTP 502, consumes 0 quota, and persists no session.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-mix-no-opt-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Explain how mitochondria produce cellular energy.",
                "question_type": "open_ended",
                "options": None,
                "correct_answer": "Mitochondria produce ATP through aerobic cellular respiration.",
                "explanation": "ATP is the energy currency synthesized in mitochondria.",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Which organelle generates ATP?",
                "question_type": "multiple_choice",
                "options": None,  # Missing options for an MCQ in mixed mode!
                "correct_answer": "Mitochondria",
                "explanation": "Mitochondria are the powerhouses of the cell.",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 2,
        "question_type": "mixed",
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_mixed_mcq_insufficient_options_fails_entirely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a targeted revision request with mixed question type where an MCQ item
    has fewer than 2 valid options fails entirely with HTTP 502, consumes 0 quota, and persists no session.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-mix-ins-opt-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Explain how mitochondria produce cellular energy.",
                "question_type": "open_ended",
                "options": None,
                "correct_answer": "Mitochondria produce ATP through aerobic cellular respiration.",
                "explanation": "ATP is the energy currency synthesized in mitochondria.",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Which organelle generates ATP?",
                "question_type": "multiple_choice",
                "options": ["Mitochondria", "   "],  # Only 1 non-empty option
                "correct_answer": "Mitochondria",
                "explanation": "Mitochondria are the powerhouses of the cell.",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 2,
        "question_type": "mixed",
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_excess_questions_rejected_fails_entirely(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a targeted revision request where the AI returns more questions than requested
    (excess questions) fails entirely with HTTP 502, consumes 0 quota, and persists no session.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-excess-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    # Requested 2 questions, but AI returned 3 questions
    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Valid Q1?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Valid Q2?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Excess Q3?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 2,
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 502

    db_session.refresh(guest)
    assert guest.ai_generation_count == 0
    assert db_session.query(RevisionSession).filter(RevisionSession.owner_id == guest.id).count() == 0


def test_api_targeted_valid_mixed_succeeds(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that a valid targeted revision request with mixed question type succeeds (HTTP 201),
    correctly sets up open-ended and multiple-choice questions, and attributes the target topic.
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-mix-ok-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    mock_ai.response_text = json.dumps({
        "topic_supported": True,
        "topic": "Cellular Respiration",
        "questions": [
            {
                "question_text": "Explain how mitochondria produce cellular energy.",
                "question_type": "open_ended",
                "options": None,
                "correct_answer": "Mitochondria produce ATP through aerobic cellular respiration.",
                "explanation": "ATP is the energy currency synthesized in mitochondria.",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
            {
                "question_text": "Which organelle generates ATP?",
                "question_type": "multiple_choice",
                "options": ["Mitochondria", "Ribosome", "Nucleus", "Vacuole"],
                "correct_answer": "Mitochondria",
                "explanation": "Mitochondria are the powerhouses of the cell.",
                "source_document_id": doc.id,
                "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            },
        ],
    })

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "topic_focus": "Cellular Respiration",
        "question_count": 2,
        "question_type": "mixed",
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201

    session_data = res.json()
    assert session_data["status"] == "in_progress"
    assert len(session_data["questions"]) == 2

    # Verify questions in database
    q1 = db_session.query(RevisionQuestion).filter(
        RevisionQuestion.session_id == session_data["id"],
        RevisionQuestion.position == 1,
    ).first()
    assert q1 is not None
    assert q1.question_type == "open_ended"
    assert q1.options is None
    assert q1.evidence_metadata.get("topic") == "Cellular Respiration"

    q2 = db_session.query(RevisionQuestion).filter(
        RevisionQuestion.session_id == session_data["id"],
        RevisionQuestion.position == 2,
    ).first()
    assert q2 is not None
    assert q2.question_type == "multiple_choice"
    assert len(q2.options) == 4
    assert q2.evidence_metadata.get("topic") == "Cellular Respiration"


def test_api_ordinary_mixed_mcq_missing_options_degrades_to_open_ended(
    test_client: TestClient,
    db_session: Session,
    mock_ai: MockMasteryAIProvider,
):
    """
    Verifies that for ordinary revision generation (without topic_focus) with mixed question type,
    an MCQ item with missing options gracefully degrades to open_ended without failing (HTTP 201).
    """
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 0
    db_session.commit()

    doc = Document(
        id=f"doc-g-ord-deg-{uuid.uuid4().hex[:8]}",
        original_filename="bio.pdf",
        stored_filename="bio.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc)
    db_session.commit()

    mock_ai.response_text = json.dumps([
        {
            "question_text": "Which organelle generates ATP?",
            "question_type": "multiple_choice",
            "options": ["Mitochondria", "Ribosome", "Nucleus", "Vacuole"],
            "correct_answer": "Mitochondria",
            "explanation": "Mitochondria generate ATP.",
            "source_document_id": doc.id,
            "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            "topic": "Cell Biology",
        },
        {
            "question_text": "What is the primary role of aerobic respiration?",
            "question_type": "multiple_choice",
            "options": None,  # Missing options in ordinary mixed mode
            "correct_answer": "To generate cellular ATP efficiently.",
            "explanation": "Aerobic respiration generates ATP.",
            "source_document_id": doc.id,
            "evidence_snippet": "Mitochondria generate cellular ATP via aerobic respiration.",
            "topic": "Cell Biology",
        },
    ])

    cookies = {settings.guest_session_cookie_name: guest.id}
    payload = {
        "document_ids": [doc.id],
        "question_count": 2,
        "question_type": "mixed",
    }
    res = test_client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
    assert res.status_code == 201

    session_data = res.json()
    assert len(session_data["questions"]) == 2

    q1 = db_session.query(RevisionQuestion).filter(
        RevisionQuestion.session_id == session_data["id"],
        RevisionQuestion.position == 1,
    ).first()
    assert q1 is not None
    assert q1.question_type == "multiple_choice"

    q2 = db_session.query(RevisionQuestion).filter(
        RevisionQuestion.session_id == session_data["id"],
        RevisionQuestion.position == 2,
    ).first()
    assert q2 is not None
    assert q2.question_type == "open_ended"
    assert q2.options is None

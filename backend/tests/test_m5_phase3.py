import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

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
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_session_service import create_guest_session
from app.services.mastery_service import calculate_mastery_for_attempts
from app.services.progress_service import get_progress_summary, get_progress_topics
from app.services.recommendation_service import get_recommendations
from app.services.spaced_repetition_service import get_review_schedules
from app.services.user_session_service import create_user_session
from app.services.weak_topic_service import detect_weak_topics


# ---------------------------------------------------------------------------
# Failing AI Provider to prove zero AI provider calls
# ---------------------------------------------------------------------------
class BombAIProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        raise RuntimeError("AI Provider was called unexpectedly!")


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
def client():
    app.dependency_overrides[get_ai_provider] = lambda: BombAIProvider()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user_a(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-p3-a-{uid}",
        email=f"user-a-{uid}@example.com",
        password_hash="pw_hash_a",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def user_b(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-p3-b-{uid}",
        email=f"user-b-{uid}@example.com",
        password_hash="pw_hash_b",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def ready_doc_user_a(db_session: Session, user_a: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-p3-a-{uid}",
        original_filename="biology_intro.pdf",
        stored_filename=f"bio_{uid}.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
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
        id=f"doc-p3-a2-{uid}",
        original_filename="genetics_intro.pdf",
        stored_filename=f"gen_{uid}.pdf",
        status="ready",
        extracted_text="DNA replication occurs during the S-phase.",
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
        id=f"doc-p3-b-{uid}",
        original_filename="chemistry_intro.pdf",
        stored_filename=f"chem_{uid}.pdf",
        status="ready",
        extracted_text="Covalent bonding involves shared electrons.",
        owner_type=IdentityType.USER.value,
        owner_id=user_b.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def auth_cookie_for_user(user: User, db: Session) -> dict[str, str]:
    session = create_user_session(db, user.id)
    return {settings.user_session_cookie_name: session.id}


# Helper to build completed sessions with questions & attempts
def create_completed_session(
    db: Session,
    owner_type: str,
    owner_id: str,
    doc: Optional[Document],
    completed_at: datetime,
    score: float = 1.0,
    mode: str = "practice",
    difficulty: str = "intermediate",
    title: str = "Revision Session",
) -> RevisionSession:
    sess = RevisionSession(
        id=f"sess-{uuid.uuid4().hex[:8]}",
        owner_type=owner_type,
        owner_id=owner_id,
        title=title,
        status="completed",
        score=score,
        total_questions=0,
        completed_at=completed_at,
        created_at=completed_at - timedelta(minutes=15),
        config={"mode": mode, "difficulty": difficulty},
    )
    db.add(sess)
    db.flush()

    if doc:
        link = RevisionSessionDocument(
            session_id=sess.id,
            document_id=doc.id,
        )
        db.add(link)

    db.commit()
    db.refresh(sess)
    return sess


def add_question_with_attempts(
    db: Session,
    session: RevisionSession,
    doc_id: Optional[str],
    doc_title: str,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    attempt_scores: Optional[list[float]] = None,
    attempt_tuples: Optional[list[tuple[float, bool]]] = None,
    created_at: Optional[datetime] = None,
) -> RevisionQuestion:
    ts = created_at or session.completed_at or datetime.now(timezone.utc)
    meta = {"document_title": doc_title}
    if doc_id:
        meta["source_document_id"] = doc_id
    if topic:
        meta["topic"] = topic
        meta["topic_key"] = topic.strip().casefold()
    if difficulty:
        meta["difficulty"] = difficulty

    session.total_questions = (session.total_questions or 0) + 1
    pos = session.total_questions

    q = RevisionQuestion(
        id=f"q-{uuid.uuid4().hex[:8]}",
        session_id=session.id,
        position=pos,
        source_document_id=doc_id,
        question_text=f"Sample question for {topic or 'general'}",
        question_type="multiple_choice",
        options=["A", "B", "C", "D"],
        correct_answer="A",
        evidence_snippet="Evidence snippet text",
        evidence_metadata=meta,
        created_at=ts,
    )
    db.add(q)
    db.flush()

    if attempt_scores:
        for idx, sc in enumerate(attempt_scores, start=1):
            is_corr = (sc >= 0.70)
            att = RevisionAttempt(
                id=f"att-{uuid.uuid4().hex[:8]}",
                session_id=session.id,
                question_id=q.id,
                attempt_number=idx,
                submitted_answer="A" if is_corr else "B",
                is_correct=is_corr,
                score=sc,
                created_at=ts,
            )
            db.add(att)
    elif attempt_tuples:
        for idx, (sc, is_corr) in enumerate(attempt_tuples, start=1):
            att = RevisionAttempt(
                id=f"att-{uuid.uuid4().hex[:8]}",
                session_id=session.id,
                question_id=q.id,
                attempt_number=idx,
                submitted_answer="A" if is_corr else "B",
                is_correct=is_corr,
                score=sc,
                created_at=ts,
            )
            db.add(att)

    db.commit()
    db.refresh(q)
    return q


# ---------------------------------------------------------------------------
# 1. API and identity isolation: zero history success
# ---------------------------------------------------------------------------
def test_endpoints_zero_history_success(client: TestClient, db_session: Session, user_a: User):
    cookies = auth_cookie_for_user(user_a, db_session)

    # 1. Summary
    res = client.get("/api/v1/progress/summary", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert data["total_completed_sessions"] == 0
    assert data["total_questions_generated"] == 0
    assert data["total_attempted_questions"] == 0
    assert data["total_unanswered_questions"] == 0
    assert data["total_attempts"] == 0
    assert data["overall_attempt_accuracy"] == 0.0
    assert data["mean_session_score"] == 0.0
    assert data["overall_mastery"]["tier"] == "unassessed"
    assert data["overall_mastery"]["is_assessed"] is False
    assert len(data["activity_timeline"]) == 30
    assert len(data["activity_windows"]["last_7_days"]["timeline"]) == 7
    assert len(data["activity_windows"]["last_14_days"]["timeline"]) == 14
    assert len(data["activity_windows"]["last_30_days"]["timeline"]) == 30
    assert len(data["difficulty_distribution"]) == 3
    assert data["flashcard_metrics"]["distinct_questions_reviewed"] == 0
    assert data["flashcard_metrics"]["recall_rate"] is None

    # 2. Topics
    res = client.get("/api/v1/progress/topics", cookies=cookies)
    assert res.status_code == 200
    assert res.json() == []

    # 3. Weak topics
    res = client.get("/api/v1/progress/weak-topics", cookies=cookies)
    assert res.status_code == 200
    assert res.json() == []

    # 4. Spaced repetition
    res = client.get("/api/v1/progress/spaced-repetition", cookies=cookies)
    assert res.status_code == 200
    assert res.json() == []

    # 5. Recommendations
    res = client.get("/api/v1/progress/recommendations", cookies=cookies)
    assert res.status_code == 200
    assert res.json() == []


# ---------------------------------------------------------------------------
# 2. Endpoints return expected data for populated history
# ---------------------------------------------------------------------------
def test_endpoints_populated_history_success(
    client: TestClient, db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(hours=2),
        score=1.0,
        difficulty="intermediate",
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Cellular Biology",
            difficulty="intermediate",
            attempt_scores=[1.0],
            created_at=now - timedelta(hours=2),
        )

    cookies = auth_cookie_for_user(user_a, db_session)

    res_sum = client.get("/api/v1/progress/summary", cookies=cookies)
    assert res_sum.status_code == 200
    s_data = res_sum.json()
    assert s_data["total_completed_sessions"] == 1
    assert s_data["total_attempted_questions"] == 3
    assert s_data["overall_attempt_accuracy"] == 1.0
    assert s_data["overall_mastery"]["is_assessed"] is True

    res_top = client.get("/api/v1/progress/topics", cookies=cookies)
    assert res_top.status_code == 200
    t_data = res_top.json()
    assert len(t_data) == 1
    assert t_data[0]["topic_display"] == "Cellular Biology"
    assert t_data[0]["is_assessed"] is True

    res_wt = client.get("/api/v1/progress/weak-topics", cookies=cookies)
    assert res_wt.status_code == 200
    assert res_wt.json() == []  # All 100%, not weak

    res_sr = client.get("/api/v1/progress/spaced-repetition", cookies=cookies)
    assert res_sr.status_code == 200
    sr_data = res_sr.json()
    assert len(sr_data) == 1
    assert sr_data[0]["current_streak"] == 1


# ---------------------------------------------------------------------------
# 3. User A cannot observe User B's progress
# ---------------------------------------------------------------------------
def test_identity_isolation_user_a_and_user_b(
    client: TestClient,
    db_session: Session,
    user_a: User,
    user_b: User,
    ready_doc_user_b: Document,
):
    now = datetime.now(timezone.utc)
    sess_b = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_b.id,
        doc=ready_doc_user_b,
        completed_at=now - timedelta(hours=1),
        score=0.9,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess_b,
            doc_id=ready_doc_user_b.id,
            doc_title=ready_doc_user_b.original_filename,
            topic="Bonding",
            attempt_scores=[0.9],
        )

    # User A requests progress
    cookies_a = auth_cookie_for_user(user_a, db_session)
    res_a = client.get("/api/v1/progress/summary", cookies=cookies_a)
    assert res_a.status_code == 200
    assert res_a.json()["total_completed_sessions"] == 0

    res_top_a = client.get("/api/v1/progress/topics", cookies=cookies_a)
    assert res_top_a.json() == []

    res_sr_a = client.get("/api/v1/progress/spaced-repetition", cookies=cookies_a)
    assert res_sr_a.json() == []

    res_rec_a = client.get("/api/v1/progress/recommendations", cookies=cookies_a)
    assert res_rec_a.json() == []


# ---------------------------------------------------------------------------
# 4. Guest and authenticated identity scoping
# ---------------------------------------------------------------------------
def test_guest_identity_scoping(client: TestClient, db_session: Session):
    guest = create_guest_session(db_session)
    doc_g = Document(
        id=f"doc-g-{uuid.uuid4().hex[:8]}",
        original_filename="guest_doc.pdf",
        stored_filename="g.pdf",
        status="ready",
        extracted_text="Guest notes on physics.",
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
    )
    db_session.add(doc_g)
    db_session.commit()

    now = datetime.now(timezone.utc)
    sess_g = create_completed_session(
        db_session,
        owner_type=IdentityType.GUEST.value,
        owner_id=guest.id,
        doc=doc_g,
        completed_at=now - timedelta(hours=1),
        score=1.0,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess_g,
            doc_id=doc_g.id,
            doc_title=doc_g.original_filename,
            topic="Thermodynamics",
            attempt_scores=[1.0],
        )

    cookies = {settings.guest_session_cookie_name: guest.id}
    res = client.get("/api/v1/progress/summary", cookies=cookies)
    assert res.status_code == 200
    assert res.json()["total_completed_sessions"] == 1

    res_top = client.get("/api/v1/progress/topics", cookies=cookies)
    assert len(res_top.json()) == 1
    assert res_top.json()[0]["topic_display"] == "Thermodynamics"


# ---------------------------------------------------------------------------
# 5. Archived document history preserved, but excluded from actions
# ---------------------------------------------------------------------------
def test_archived_document_history_preserved_but_excluded_from_actions(
    client: TestClient, db_session: Session, user_a: User
):
    now = datetime.now(timezone.utc)
    # Session with deleted/archived document (doc_id is not in documents table)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=None,
        completed_at=now - timedelta(days=2),
        score=0.2,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id="deleted-doc-999",
            doc_title="Deleted Text.pdf",
            topic="Old Topic",
            attempt_scores=[0.2],
            created_at=now - timedelta(days=2),
        )

    cookies = auth_cookie_for_user(user_a, db_session)

    # In topics: shows as archived
    res_top = client.get("/api/v1/progress/topics", cookies=cookies)
    top_data = res_top.json()
    assert len(top_data) == 1
    assert top_data[0]["is_archived"] is True

    # In weak topics: shows as archived, is_actionable is False
    res_wt = client.get("/api/v1/progress/weak-topics", cookies=cookies)
    wt_data = res_wt.json()
    assert len(wt_data) == 1
    assert wt_data[0]["is_archived"] is True
    assert wt_data[0]["is_actionable"] is False

    # In spaced repetition: shows as archived, is_actionable is False
    res_sr = client.get("/api/v1/progress/spaced-repetition", cookies=cookies)
    sr_data = res_sr.json()
    assert len(sr_data) == 1
    assert sr_data[0]["is_archived"] is True
    assert sr_data[0]["is_actionable"] is False

    # In recommendations: MUST NEVER appear as an actionable recommendation
    res_rec = client.get("/api/v1/progress/recommendations", cookies=cookies)
    rec_data = res_rec.json()
    assert len(rec_data) == 0


# ---------------------------------------------------------------------------
# 6. Guest quota left unchanged
# ---------------------------------------------------------------------------
def test_all_endpoints_preserve_guest_ai_quota(client: TestClient, db_session: Session):
    guest = create_guest_session(db_session)
    guest.ai_generation_count = 2
    db_session.commit()

    cookies = {settings.guest_session_cookie_name: guest.id}
    endpoints = [
        "/api/v1/progress/summary",
        "/api/v1/progress/topics",
        "/api/v1/progress/weak-topics",
        "/api/v1/progress/spaced-repetition",
        "/api/v1/progress/recommendations",
    ]
    for ep in endpoints:
        res = client.get(ep, cookies=cookies)
        assert res.status_code == 200

    db_session.refresh(guest)
    assert guest.ai_generation_count == 2


# ---------------------------------------------------------------------------
# 7. No AI provider calls
# ---------------------------------------------------------------------------
def test_zero_ai_provider_calls(client: TestClient, db_session: Session, user_a: User):
    cookies = auth_cookie_for_user(user_a, db_session)
    # If any endpoint called AIProvider, BombAIProvider would raise RuntimeError and return 500
    for ep in [
        "/api/v1/progress/summary",
        "/api/v1/progress/topics",
        "/api/v1/progress/weak-topics",
        "/api/v1/progress/spaced-repetition",
        "/api/v1/progress/recommendations",
    ]:
        res = client.get(ep, cookies=cookies)
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# 8. Endpoints do not mutate persisted database state
# ---------------------------------------------------------------------------
def test_read_only_endpoints_no_database_mutation(
    client: TestClient, db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(hours=1),
        score=0.8,
    )
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        topic="Genetics",
        attempt_scores=[0.8],
    )

    before_sessions = db_session.query(RevisionSession).count()
    before_questions = db_session.query(RevisionQuestion).count()
    before_attempts = db_session.query(RevisionAttempt).count()

    cookies = auth_cookie_for_user(user_a, db_session)
    for ep in [
        "/api/v1/progress/summary",
        "/api/v1/progress/topics",
        "/api/v1/progress/weak-topics",
        "/api/v1/progress/spaced-repetition",
        "/api/v1/progress/recommendations",
    ]:
        res = client.get(ep, cookies=cookies)
        assert res.status_code == 200

    after_sessions = db_session.query(RevisionSession).count()
    after_questions = db_session.query(RevisionQuestion).count()
    after_attempts = db_session.query(RevisionAttempt).count()

    assert before_sessions == after_sessions
    assert before_questions == after_questions
    assert before_attempts == after_attempts


# ---------------------------------------------------------------------------
# 9. Router paths registered exactly once under expected prefix
# ---------------------------------------------------------------------------
def test_router_registration_and_exact_paths(client: TestClient):
    routes = [route.path for route in app.routes]
    expected_paths = [
        "/api/v1/progress/summary",
        "/api/v1/progress/topics",
        "/api/v1/progress/weak-topics",
        "/api/v1/progress/spaced-repetition",
        "/api/v1/progress/recommendations",
    ]
    for ep in expected_paths:
        matches = [r for r in routes if r == ep]
        assert len(matches) == 1, f"Path {ep} was expected exactly once, found {len(matches)}"


# ---------------------------------------------------------------------------
# 10. Attempt accuracy uses each question's latest attempt, not retries
# ---------------------------------------------------------------------------
def test_attempt_accuracy_uses_latest_attempt_not_retries(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
    )
    # Question 1: attempt 1 = 0.0, attempt 2 = 1.0 (latest is 1.0)
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[0.0, 1.0],
    )
    # Question 2: attempt 1 = 1.0, attempt 2 = 0.5 (latest is 0.5)
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0, 0.5],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=now)

    # Total distinct attempted questions = 2, total attempts = 4
    assert summary.total_attempted_questions == 2
    assert summary.total_attempts == 4
    # Expected latest attempts: 1.0 and 0.5 -> average = 0.75
    assert summary.overall_attempt_accuracy == 0.75


# ---------------------------------------------------------------------------
# 11. Mean official session score reported separately from attempt accuracy
# ---------------------------------------------------------------------------
def test_mean_session_score_reported_separately_from_attempt_accuracy(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    # Session 1: official score = 0.5
    sess1 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=1),
        score=0.5,
    )
    add_question_with_attempts(
        db_session,
        sess1,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )

    # Session 2: official score = 0.7
    sess2 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
        score=0.7,
    )
    add_question_with_attempts(
        db_session,
        sess2,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=now)

    assert summary.overall_attempt_accuracy == 1.0
    assert summary.mean_session_score == round((0.5 + 0.7) / 2, 4)


# ---------------------------------------------------------------------------
# 12. Unanswered questions excluded from attempt accuracy but in session scores
# ---------------------------------------------------------------------------
def test_unanswered_questions_excluded_from_attempt_accuracy(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
        score=0.25,
    )
    # 1 answered question (score 1.0)
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )
    # 3 unanswered questions (attempt_scores=None)
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            attempt_scores=None,
        )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=now)

    assert summary.total_questions_generated == 4
    assert summary.total_attempted_questions == 1
    assert summary.total_unanswered_questions == 3
    assert summary.overall_attempt_accuracy == 1.0
    assert summary.mean_session_score == 0.25


# ---------------------------------------------------------------------------
# 13. Completed-session counts and question-attempt counts
# ---------------------------------------------------------------------------
def test_completed_session_counts_and_attempt_counts(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    # Completed session
    sess_done = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
        score=1.0,
    )
    add_question_with_attempts(
        db_session,
        sess_done,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )

    # In-progress session (must NOT be counted)
    sess_prog = RevisionSession(
        id=f"sess-prog-{uuid.uuid4().hex[:8]}",
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        title="In-Progress",
        status="in_progress",
        total_questions=1,
    )
    db_session.add(sess_prog)
    db_session.commit()
    add_question_with_attempts(
        db_session,
        sess_prog,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=now)
    assert summary.total_completed_sessions == 1
    assert summary.total_attempted_questions == 1


# ---------------------------------------------------------------------------
# 14. Activity timeline continuous 30-day UTC buckets
# ---------------------------------------------------------------------------
def test_activity_timeline_continuous_30_days_utc(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    fixed_now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Session 5 days ago
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=fixed_now - timedelta(days=5),
        score=0.8,
    )
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[0.8],
        created_at=fixed_now - timedelta(days=5),
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=fixed_now)

    timeline = summary.activity_timeline
    assert len(timeline) == 30
    assert timeline[-1].date == "2026-10-15"
    assert timeline[0].date == "2026-09-16"

    # Day 5 days ago (2026-10-10) should have 1 attempt and score 0.8
    day_target = [d for d in timeline if d.date == "2026-10-10"][0]
    assert day_target.total_attempts == 1
    assert day_target.average_score == 0.8

    # Windows
    assert summary.activity_windows.last_7_days.total_attempts == 1
    assert summary.activity_windows.last_7_days.average_score == 0.8
    assert summary.activity_windows.last_14_days.total_attempts == 1
    assert summary.activity_windows.last_30_days.total_attempts == 1


# ---------------------------------------------------------------------------
# 15. Difficulty distribution metadata & counts
# ---------------------------------------------------------------------------
def test_difficulty_distribution_metadata(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
    )
    # 2 beginner questions
    for _ in range(2):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            difficulty="beginner",
            attempt_scores=[1.0],
        )
    # 1 advanced question
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        difficulty="advanced",
        attempt_scores=[0.5],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=now)

    diff_map = {d.difficulty: d for d in summary.difficulty_distribution}
    assert diff_map["beginner"].distinct_attempted_questions == 2
    assert diff_map["beginner"].average_score == 1.0
    assert diff_map["intermediate"].distinct_attempted_questions == 0
    assert diff_map["advanced"].distinct_attempted_questions == 1
    assert diff_map["advanced"].average_score == 0.5


# ---------------------------------------------------------------------------
# 16. Flashcard metrics mode filtering
# ---------------------------------------------------------------------------
def test_flashcard_metrics_mode_filtering(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    # Practice session
    sess_prac = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
        mode="practice",
    )
    add_question_with_attempts(
        db_session,
        sess_prac,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )

    # Flashcard session
    sess_fc = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
        mode="flashcards",
    )
    add_question_with_attempts(
        db_session,
        sess_fc,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=now)

    assert summary.flashcard_metrics.distinct_questions_reviewed == 1
    assert summary.flashcard_metrics.recall_rate == 1.0


# ---------------------------------------------------------------------------
# 17. Flashcard recall and insufficient data behavior
# ---------------------------------------------------------------------------
def test_flashcard_recall_and_insufficient_data(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess_fc = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
        mode="flashcards",
    )
    # Only 2 attempts (insufficient for assessed tier)
    add_question_with_attempts(
        db_session,
        sess_fc,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )
    add_question_with_attempts(
        db_session,
        sess_fc,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[0.0],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    summary = get_progress_summary(db_session, ident, now=now)

    fc = summary.flashcard_metrics
    assert fc.distinct_questions_reviewed == 2
    assert fc.recall_rate == 0.5
    assert fc.mastery.tier == "unassessed"
    assert fc.mastery.is_assessed is False
    assert fc.mastery.questions_needed == 1


# ---------------------------------------------------------------------------
# 18. Composite topic grouping does not merge identical labels across docs
# ---------------------------------------------------------------------------
def test_composite_topic_grouping_separate_across_documents(
    db_session: Session,
    user_a: User,
    ready_doc_user_a: Document,
    ready_doc_2_user_a: Document,
):
    now = datetime.now(timezone.utc)
    sess1 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess1,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Cell Biology",
            attempt_scores=[1.0],
        )

    sess2 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_2_user_a,
        completed_at=now,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess2,
            doc_id=ready_doc_2_user_a.id,
            doc_title=ready_doc_2_user_a.original_filename,
            topic="Cell Biology",
            attempt_scores=[0.5],
        )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    topics = get_progress_topics(db_session, ident, now=now)

    # Must be 2 separate entries for the 2 documents
    assert len(topics) == 2
    doc_ids = {t.document_id for t in topics}
    assert doc_ids == {ready_doc_user_a.id, ready_doc_2_user_a.id}


# ---------------------------------------------------------------------------
# 19. Legacy unattributed questions do not acquire synthetic topics
# ---------------------------------------------------------------------------
def test_legacy_unattributed_questions_no_synthetic_topics(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
    )
    # Question with no topic metadata
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        topic=None,
        attempt_scores=[1.0],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    topics = get_progress_topics(db_session, ident, now=now)
    assert len(topics) == 0


# ---------------------------------------------------------------------------
# 20. Topic mastery decay and assessment thresholds
# ---------------------------------------------------------------------------
def test_topic_mastery_decay_and_assessment_threshold(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Mitosis",
            attempt_scores=[1.0],
        )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    topics = get_progress_topics(db_session, ident, now=now)
    assert len(topics) == 1
    t = topics[0]
    assert t.is_assessed is True
    assert t.mastery_tier == "mastered"
    assert t.mastery_score == 1.0


# ---------------------------------------------------------------------------
# 21. Weak topic boundary condition (50% incorrect does not qualify alone)
# ---------------------------------------------------------------------------
def test_weak_topic_50_percent_boundary_and_struggle_index(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
    )
    # 4 questions in Topic 1: 2 correct (1.0), 2 incorrect (0.0) -> incorrect ratio = 2/4 = 0.50 exactly.
    # Score is 0.50, which is < 0.60, so it qualifies under mastery < 0.60.
    # To test the boundary where incorrect_ratio is 0.50 and mastery >= 0.60:
    # 2 questions at 1.0, 2 questions at 0.40 -> average = 0.70 (>= 0.60), but is_correct for 0.40 is False!
    # Incorrect count = 2/4 = 0.50. Mastery >= 0.60. So neither condition triggers!
    for _ in range(2):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Boundary Topic",
            attempt_tuples=[(1.0, True)],
        )
    for _ in range(2):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Boundary Topic",
            attempt_tuples=[(0.65, False)],
        )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    wt = detect_weak_topics(db_session, ident, now=now)
    # Mastery score is around 0.825 (>= 0.60) and incorrect ratio is 0.50 (not > 0.50), so NOT weak
    assert len(wt) == 0


# ---------------------------------------------------------------------------
# 22. Spaced repetition raw-threshold decision (0.69996 vs 0.70)
# ---------------------------------------------------------------------------
def test_spaced_repetition_raw_threshold_precision(
    db_session: Session,
    user_a: User,
    ready_doc_user_a: Document,
    ready_doc_2_user_a: Document,
):
    now = datetime.now(timezone.utc)
    # Doc 1: average 0.69996 -> FAIL
    sess1 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
        score=0.69996,
    )
    add_question_with_attempts(
        db_session,
        sess1,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[0.69996],
    )

    # Doc 2: average 0.70 -> SUCCESS
    sess2 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_2_user_a,
        completed_at=now,
        score=0.70,
    )
    add_question_with_attempts(
        db_session,
        sess2,
        doc_id=ready_doc_2_user_a.id,
        doc_title=ready_doc_2_user_a.original_filename,
        attempt_scores=[0.70],
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    schedules = get_review_schedules(db_session, ident, now=now)

    sched_map = {s.document_id: s for s in schedules}
    # Doc 1 failed -> streak 0, interval 1
    assert sched_map[ready_doc_user_a.id].current_streak == 0
    assert sched_map[ready_doc_user_a.id].interval_days == 1

    # Doc 2 succeeded -> streak 1, interval 1
    assert sched_map[ready_doc_2_user_a.id].current_streak == 1
    assert sched_map[ready_doc_2_user_a.id].interval_days == 1


# ---------------------------------------------------------------------------
# 23. Due recommendations urgency >= 1.0; not-yet-due reviews excluded
# ---------------------------------------------------------------------------
def test_due_recommendations_urgency_and_not_due_exclusion(
    db_session: Session,
    user_a: User,
    ready_doc_user_a: Document,
    ready_doc_2_user_a: Document,
):
    now = datetime.now(timezone.utc)
    # Doc 1: reviewed 3 days ago with streak 0 (interval 1 day) -> DUE (2 days overdue, urgency ~ 3.0)
    sess1 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=3),
        score=0.5,
    )
    add_question_with_attempts(
        db_session,
        sess1,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[0.5],
        created_at=now - timedelta(days=3),
    )

    # Doc 2: reviewed 2 hours ago with score 1.0 (streak 1, interval 1 day, due in 22 hours) -> NOT DUE
    sess2 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_2_user_a,
        completed_at=now - timedelta(hours=2),
        score=1.0,
    )
    add_question_with_attempts(
        db_session,
        sess2,
        doc_id=ready_doc_2_user_a.id,
        doc_title=ready_doc_2_user_a.original_filename,
        attempt_scores=[1.0],
        created_at=now - timedelta(hours=2),
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    recs = get_recommendations(db_session, ident, now=now)

    due_recs = [r for r in recs if r.type == "spaced_review"]
    assert len(due_recs) == 1
    assert due_recs[0].document_id == ready_doc_user_a.id
    assert due_recs[0].urgency is not None
    assert due_recs[0].urgency >= 1.0


# ---------------------------------------------------------------------------
# 24. Weak-topic recommendations preserve topic focus
# ---------------------------------------------------------------------------
def test_weak_topic_recommendation_preserves_topic_focus(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Krebs Cycle",
            attempt_scores=[0.2],
        )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    recs = get_recommendations(db_session, ident, now=now)

    wt_recs = [r for r in recs if r.type == "weak_topic_practice"]
    assert len(wt_recs) == 1
    rec = wt_recs[0]
    assert rec.priority == 2
    assert rec.document_id == ready_doc_user_a.id
    assert rec.topic_focus == "Krebs Cycle"
    assert rec.action_payload.topic_focus == "Krebs Cycle"
    assert rec.action_payload.document_ids == [ready_doc_user_a.id]


# ---------------------------------------------------------------------------
# 25. Unrevised document recommendations exclude revised documents
# ---------------------------------------------------------------------------
def test_unrevised_document_recommendation_excludes_revised_documents(
    db_session: Session,
    user_a: User,
    ready_doc_user_a: Document,
    ready_doc_2_user_a: Document,
):
    now = datetime.now(timezone.utc)
    # Doc 1 has revision session
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=1),
        score=1.0,
    )
    add_question_with_attempts(
        db_session,
        sess,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[1.0],
    )
    # Doc 2 has NO revision history

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    recs = get_recommendations(db_session, ident, now=now)

    unrev_recs = [r for r in recs if r.type == "unrevised_document"]
    assert len(unrev_recs) == 1
    assert unrev_recs[0].document_id == ready_doc_2_user_a.id
    assert unrev_recs[0].priority == 3


# ---------------------------------------------------------------------------
# 26. Recommendation ordering is deterministic across repeated calls
# ---------------------------------------------------------------------------
def test_recommendation_ordering_deterministic_and_stable(
    db_session: Session,
    user_a: User,
    ready_doc_user_a: Document,
    ready_doc_2_user_a: Document,
):
    now = datetime.now(timezone.utc)
    ident = Identity(type=IdentityType.USER, id=user_a.id)

    recs1 = get_recommendations(db_session, ident, now=now)
    recs2 = get_recommendations(db_session, ident, now=now)

    ids1 = [r.id for r in recs1]
    ids2 = [r.id for r in recs2]
    assert ids1 == ids2


# ---------------------------------------------------------------------------
# 27. Recommendation action payload parameters
# ---------------------------------------------------------------------------
def test_recommendation_action_payload_format(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    ident = Identity(type=IdentityType.USER, id=user_a.id)
    recs = get_recommendations(db_session, ident, now=now)

    assert len(recs) == 1
    payload = recs[0].action_payload
    assert payload.document_ids == [ready_doc_user_a.id]
    assert payload.mode == "practice"
    assert payload.difficulty == "intermediate"
    assert payload.question_count == 5
    assert payload.question_type == "multiple_choice"


# ---------------------------------------------------------------------------
# 28. Archived documents never generate recommendation actions
# ---------------------------------------------------------------------------
def test_archived_documents_never_generate_recommendations(
    db_session: Session, user_a: User
):
    now = datetime.now(timezone.utc)
    # Session with historical deleted document
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=None,
        completed_at=now - timedelta(days=10),
        score=0.1,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id="deleted-doc-xyz",
            doc_title="Deleted.pdf",
            topic="Dead Topic",
            attempt_scores=[0.1],
        )

    ident = Identity(type=IdentityType.USER, id=user_a.id)
    recs = get_recommendations(db_session, ident, now=now)
    assert len(recs) == 0


# ---------------------------------------------------------------------------
# 29. No-history schedules produce no due-date recommendations
# ---------------------------------------------------------------------------
def test_no_history_schedules_produce_no_due_recommendations(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    ident = Identity(type=IdentityType.USER, id=user_a.id)
    schedules = get_review_schedules(
        db_session, ident, now=now, include_unreviewed_active=True
    )
    assert len(schedules) == 1
    assert schedules[0].has_history is False
    assert schedules[0].is_due is False

    recs = get_recommendations(db_session, ident, now=now)
    sr_recs = [r for r in recs if r.type == "spaced_review"]
    assert len(sr_recs) == 0


# ---------------------------------------------------------------------------
# 30. Read-only calls do not create persistent recommendation state
# ---------------------------------------------------------------------------
def test_read_only_calls_do_not_persist_state(
    client: TestClient, db_session: Session, user_a: User, ready_doc_user_a: Document
):
    cookies = auth_cookie_for_user(user_a, db_session)

    # Initial state
    c1 = db_session.query(RevisionSession).count()
    c2 = db_session.query(RevisionQuestion).count()
    c3 = db_session.query(RevisionAttempt).count()

    for _ in range(3):
        res = client.get("/api/v1/progress/recommendations", cookies=cookies)
        assert res.status_code == 200

    assert db_session.query(RevisionSession).count() == c1
    assert db_session.query(RevisionQuestion).count() == c2
    assert db_session.query(RevisionAttempt).count() == c3


# ---------------------------------------------------------------------------
# Document Readiness Actionability Tests (Phase 3 Follow-up)
# ---------------------------------------------------------------------------

def test_actionability_ready_with_text_produces_recommendations(
    client: TestClient, db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    # 1. Unrevised ready document with text produces unrevised_document recommendation
    ident = Identity(type=IdentityType.USER, id=user_a.id)
    recs = get_recommendations(db_session, ident, now=now)
    assert len(recs) == 1
    assert recs[0].type == "unrevised_document"
    assert recs[0].document_id == ready_doc_user_a.id
    assert recs[0].is_actionable is True

    # 2. Add due session and weak topic
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=3),
        score=0.2,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Enzyme Kinetics",
            attempt_scores=[0.2],
            created_at=now - timedelta(days=3),
        )

    # Check spaced repetition and weak topics report is_actionable=True
    schedules = get_review_schedules(db_session, ident, now=now)
    assert len(schedules) == 1
    assert schedules[0].is_archived is False
    assert schedules[0].is_actionable is True

    wts = detect_weak_topics(db_session, ident, now=now)
    assert len(wts) == 1
    assert wts[0].is_archived is False
    assert wts[0].is_actionable is True

    # Both spaced_review and weak_topic_practice are recommended
    recs_after = get_recommendations(db_session, ident, now=now)
    types = [r.type for r in recs_after]
    assert "spaced_review" in types
    assert "weak_topic_practice" in types


def test_actionability_failed_document_preserves_history_but_is_not_actionable(
    client: TestClient, db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=3),
        score=0.2,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Enzyme Kinetics",
            attempt_scores=[0.2],
            created_at=now - timedelta(days=3),
        )

    # Now document status changes to "failed"
    ready_doc_user_a.status = "failed"
    db_session.commit()

    cookies = auth_cookie_for_user(user_a, db_session)

    # 1. Topic mastery preserved, is_archived=False
    res_top = client.get("/api/v1/progress/topics", cookies=cookies)
    assert res_top.status_code == 200
    top_data = res_top.json()
    assert len(top_data) == 1
    assert top_data[0]["is_archived"] is False
    assert top_data[0]["topic_display"] == "Enzyme Kinetics"

    # 2. Weak topics preserved, is_archived=False, but is_actionable=False
    res_wt = client.get("/api/v1/progress/weak-topics", cookies=cookies)
    assert res_wt.status_code == 200
    wt_data = res_wt.json()
    assert len(wt_data) == 1
    assert wt_data[0]["is_archived"] is False
    assert wt_data[0]["is_actionable"] is False

    # 3. Spaced repetition preserved, is_archived=False, but is_actionable=False
    res_sr = client.get("/api/v1/progress/spaced-repetition", cookies=cookies)
    assert res_sr.status_code == 200
    sr_data = res_sr.json()
    assert len(sr_data) == 1
    assert sr_data[0]["is_archived"] is False
    assert sr_data[0]["is_actionable"] is False
    assert sr_data[0]["has_history"] is True

    # 4. Recommendations: ZERO recommendations produced for the failed document
    res_rec = client.get("/api/v1/progress/recommendations", cookies=cookies)
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert len(rec_data) == 0


def test_actionability_processing_document_is_not_actionable(
    client: TestClient, db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=3),
        score=0.2,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Enzyme Kinetics",
            attempt_scores=[0.2],
            created_at=now - timedelta(days=3),
        )

    # Document is in "processing" state
    ready_doc_user_a.status = "processing"
    db_session.commit()

    cookies = auth_cookie_for_user(user_a, db_session)

    res_wt = client.get("/api/v1/progress/weak-topics", cookies=cookies)
    assert res_wt.json()[0]["is_actionable"] is False

    res_sr = client.get("/api/v1/progress/spaced-repetition", cookies=cookies)
    assert res_sr.json()[0]["is_actionable"] is False

    res_rec = client.get("/api/v1/progress/recommendations", cookies=cookies)
    assert len(res_rec.json()) == 0


def test_actionability_empty_or_whitespace_text_is_not_actionable(
    client: TestClient, db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    sess = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=3),
        score=0.2,
    )
    for _ in range(3):
        add_question_with_attempts(
            db_session,
            sess,
            doc_id=ready_doc_user_a.id,
            doc_title=ready_doc_user_a.original_filename,
            topic="Enzyme Kinetics",
            attempt_scores=[0.2],
            created_at=now - timedelta(days=3),
        )

    # Document is ready, but extracted_text is whitespace only
    ready_doc_user_a.extracted_text = "   \n\t  "
    db_session.commit()

    cookies = auth_cookie_for_user(user_a, db_session)

    res_wt = client.get("/api/v1/progress/weak-topics", cookies=cookies)
    assert res_wt.json()[0]["is_actionable"] is False

    res_sr = client.get("/api/v1/progress/spaced-repetition", cookies=cookies)
    assert res_sr.json()[0]["is_actionable"] is False

    res_rec = client.get("/api/v1/progress/recommendations", cookies=cookies)
    assert len(res_rec.json()) == 0


def test_document_becoming_ineligible_does_not_erase_history_or_streaks(
    db_session: Session, user_a: User, ready_doc_user_a: Document
):
    now = datetime.now(timezone.utc)
    # 2 successful sessions -> streak 2, interval 3
    s1 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=5),
        score=0.9,
    )
    add_question_with_attempts(
        db_session,
        s1,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[0.9],
        created_at=now - timedelta(days=5),
    )

    s2 = create_completed_session(
        db_session,
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
        doc=ready_doc_user_a,
        completed_at=now - timedelta(days=4),
        score=0.95,
    )
    add_question_with_attempts(
        db_session,
        s2,
        doc_id=ready_doc_user_a.id,
        doc_title=ready_doc_user_a.original_filename,
        attempt_scores=[0.95],
        created_at=now - timedelta(days=4),
    )

    ident = Identity(type=IdentityType.USER, id=user_a.id)

    # Verify initial streak 2
    sched_init = get_review_schedules(db_session, ident, now=now)[0]
    assert sched_init.current_streak == 2
    assert sched_init.interval_days == 3
    assert sched_init.is_actionable is True
    assert sched_init.is_archived is False

    # Document fails
    ready_doc_user_a.status = "failed"
    db_session.commit()

    sched_failed = get_review_schedules(db_session, ident, now=now)[0]
    assert sched_failed.current_streak == 2
    assert sched_failed.interval_days == 3
    assert sched_failed.is_actionable is False
    assert sched_failed.is_archived is False

    # Document reprocessed and becomes ready again
    ready_doc_user_a.status = "ready"
    db_session.commit()

    sched_recovered = get_review_schedules(db_session, ident, now=now)[0]
    assert sched_recovered.current_streak == 2
    assert sched_recovered.interval_days == 3
    assert sched_recovered.is_actionable is True
    assert sched_recovered.is_archived is False

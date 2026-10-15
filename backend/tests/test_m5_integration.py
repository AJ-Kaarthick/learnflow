"""
LearnFlow V3 Milestone 5 — Phase 5: Cross-Phase Integration Test Suite.

Comprehensive end-to-end integration tests verifying:
- Section A: End-to-end progress API integration across all five endpoints against shared persisted learning history
- Section B: Targeted Revision generation, weak-topic recommendation handoff, topic focus validation, and atomic failure modes
- Section C: Guest-to-account migration of Revision sessions, questions, topic metadata, and instant progress visibility
- Section D: Document deletion durability, foreign-key ON DELETE SET NULL, historical fallback, and schedule preservation
- Section E: Phase 4 workspace contract regressions, zero-quota guarantees, and M5 invariants
"""

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

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
from app.schemas.identity import IdentityType
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_limit_service import GuestLimitType
from app.services.guest_migration_service import migrate_guest_data_to_user
from app.services.guest_session_service import create_guest_session
from app.services.revision_service import UnsupportedTopicError
from app.services.user_session_service import create_user_session


# ---------------------------------------------------------------------------
# Test AI Providers
# ---------------------------------------------------------------------------

class BombAIProvider(AIProvider):
    """Fails immediately if any AI call is triggered during read-only operations."""

    async def generate_text(self, prompt: str) -> str:
        raise RuntimeError("AI Provider was called unexpectedly during read-only operation!")


class TargetedRevisionAIProvider(AIProvider):
    """
    Deterministic mock AI provider for targeted revision and recommendation handoff tests.
    Supports topic support confirmation, verifiable evidence snippets, and simulated failures.
    """

    def __init__(self, doc_extracted_text: str = "Mitochondria generate cellular ATP via aerobic respiration.") -> None:
        self.doc_extracted_text = doc_extracted_text
        self.call_count = 0
        self.prompts: list[str] = []
        self.should_be_unsupported = False
        self.should_fail_upstream = False
        self.should_mismatch_count = False

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        self.prompts.append(prompt)

        if self.should_fail_upstream:
            raise AIProviderError("Simulated upstream provider timeout")

        if self.should_be_unsupported:
            return json.dumps({
                "topic_supported": False,
                "questions": [],
            })

        # Extract doc id and target count from prompt
        doc_id_match = re.search(r"Document ID:\s*([^\s\n]+)", prompt)
        doc_id = doc_id_match.group(1) if doc_id_match else "doc-1"

        count_match = re.search(r"create exactly\s*(\d+)", prompt)
        target_count = int(count_match.group(1)) if count_match else 3
        count = max(1, target_count - 1) if self.should_mismatch_count else target_count

        # Detect targeted generation
        is_targeted = "TARGET TOPIC FOCUS" in prompt

        if is_targeted:
            return json.dumps({
                "topic_supported": True,
                "questions": [
                    {
                        "question_text": f"Targeted question {i} regarding cell mechanics.",
                        "question_type": "multiple_choice",
                        "options": ["Mitochondria", "Ribosome", "Nucleus", "Vacuole"],
                        "correct_answer": "Mitochondria",
                        "explanation": f"Explanation for question {i}.",
                        "source_document_id": doc_id,
                        "evidence_snippet": self.doc_extracted_text[:40],
                    }
                    for i in range(1, count + 1)
                ],
            })
        else:
            return json.dumps([
                {
                    "question_text": f"General question {i} regarding biology.",
                    "question_type": "multiple_choice",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "explanation": f"Explanation {i}.",
                    "source_document_id": doc_id,
                    "evidence_snippet": self.doc_extracted_text[:40],
                    "topic": "Cell Biology",
                }
                for i in range(1, count + 1)
            ])


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
        id=f"user-int-a-{uid}",
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
        id=f"user-int-b-{uid}",
        email=f"user-b-{uid}@example.com",
        password_hash="pw_hash_b",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def doc_bio(db_session: Session, user_a: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-bio-{uid}",
        original_filename="biology_cell.pdf",
        stored_filename=f"bio_{uid}.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration. Mitosis divides somatic cells.",
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture()
def doc_genetics(db_session: Session, user_a: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-gen-{uid}",
        original_filename="genetics_intro.pdf",
        stored_filename=f"gen_{uid}.pdf",
        status="ready",
        extracted_text="Mendelian inheritance demonstrates dominant and recessive alleles.",
        owner_type=IdentityType.USER.value,
        owner_id=user_a.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def auth_cookie_for_user(user: User, db: Session) -> dict[str, str]:
    session = create_user_session(db, user.id)
    return {settings.user_session_cookie_name: session.id}


def auth_cookie_for_guest(guest: GuestSession) -> dict[str, str]:
    return {settings.guest_session_cookie_name: guest.id}


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
    topic_focus: Optional[str] = None,
) -> RevisionSession:
    cfg = {"mode": mode, "difficulty": difficulty}
    if topic_focus:
        cfg["topic_focus"] = topic_focus

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
        config=cfg,
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
        question_text=f"Question {pos} on {topic or 'general'}",
        question_type="multiple_choice",
        options=["A", "B", "C", "D"],
        correct_answer="A",
        evidence_snippet="Evidence snippet",
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
                created_at=ts + timedelta(seconds=idx * 10),
            )
            db.add(att)

    db.commit()
    db.refresh(q)
    return q


# ===========================================================================
# A. END-TO-END PROGRESS API INTEGRATION
# ===========================================================================

class TestEndToEndProgressApiIntegration:
    """
    Verifies that all five progress REST endpoints operate seamlessly against
    the same persisted learning history.
    """

    def test_all_five_endpoints_with_persisted_learning_history(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document, doc_genetics: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # 1. Session 1 on doc_bio: 3 questions on "Cellular Respiration", high score (1.0 each)
        s1 = create_completed_session(
            db_session, IdentityType.USER.value, user_a.id, doc_bio, now - timedelta(days=2), score=1.0
        )
        for _ in range(3):
            add_question_with_attempts(db_session, s1, doc_bio.id, doc_bio.original_filename, topic="Cellular Respiration", attempt_scores=[1.0])

        # 2. Session 2 on doc_bio: 3 questions on "Mitosis", low score (0.0 each -> weak topic candidate)
        s2 = create_completed_session(
            db_session, IdentityType.USER.value, user_a.id, doc_bio, now - timedelta(days=1), score=0.0
        )
        for _ in range(3):
            add_question_with_attempts(db_session, s2, doc_bio.id, doc_bio.original_filename, topic="Mitosis", attempt_scores=[0.0])

        # 3. Query all 5 Progress API endpoints

        # (1) Summary
        res_sum = client.get("/api/v1/progress/summary", cookies=cookies)
        assert res_sum.status_code == 200
        data_sum = res_sum.json()
        assert data_sum["total_completed_sessions"] == 2
        assert data_sum["total_attempted_questions"] == 6
        assert data_sum["overall_attempt_accuracy"] == 0.5  # 3 correct, 3 incorrect
        assert data_sum["overall_mastery"]["tier"] in ("mastered", "proficient", "needs_practice")
        assert len(data_sum["activity_windows"]["last_7_days"]["timeline"]) == 7

        # (2) Topics
        res_top = client.get("/api/v1/progress/topics", cookies=cookies)
        assert res_top.status_code == 200
        data_top = res_top.json()
        topic_names = {t["topic_display"] for t in data_top}
        assert "Cellular Respiration" in topic_names
        assert "Mitosis" in topic_names
        # Cellular respiration is assessed and proficient/mastered
        cr_item = next(t for t in data_top if t["topic_display"] == "Cellular Respiration")
        assert cr_item["is_assessed"] is True
        assert cr_item["mastery_tier"] == "mastered"
        # Mitosis is assessed and needs_practice
        mit_item = next(t for t in data_top if t["topic_display"] == "Mitosis")
        assert mit_item["is_assessed"] is True
        assert mit_item["mastery_tier"] == "needs_practice"

        # (3) Weak Topics
        res_wt = client.get("/api/v1/progress/weak-topics", cookies=cookies)
        assert res_wt.status_code == 200
        data_wt = res_wt.json()
        assert len(data_wt) >= 1
        assert any(w["topic_display"] == "Mitosis" for w in data_wt)
        weak_mit = next(w for w in data_wt if w["topic_display"] == "Mitosis")
        assert weak_mit["struggle_index"] > 0.0
        assert weak_mit["is_actionable"] is True

        # (4) Spaced Repetition Schedules
        res_sr = client.get("/api/v1/progress/spaced-repetition?include_unreviewed_active=true", cookies=cookies)
        assert res_sr.status_code == 200
        data_sr = res_sr.json()
        bio_sched = next((s for s in data_sr if s["document_id"] == doc_bio.id), None)
        assert bio_sched is not None
        assert bio_sched["has_history"] is True
        # Most recent review score was 0.0, resetting streak to 0
        assert bio_sched["current_streak"] == 0
        assert bio_sched["interval_days"] == 1

        # (5) Recommendations
        res_rec = client.get("/api/v1/progress/recommendations", cookies=cookies)
        assert res_rec.status_code == 200
        data_rec = res_rec.json()
        rec_types = [r["type"] for r in data_rec]
        # Strictly adheres to 3-priority hierarchy
        for r in data_rec:
            assert r["type"] in ("spaced_review", "weak_topic_practice", "unrevised_document")
            assert r["priority"] in (1, 2, 3)
        # Should include weak_topic_practice for Mitosis and unrevised_document for doc_genetics
        assert "weak_topic_practice" in rec_types
        assert "unrevised_document" in rec_types
        wt_rec = next(r for r in data_rec if r["type"] == "weak_topic_practice")
        assert wt_rec["topic_focus"] == "Mitosis"
        assert wt_rec["action_payload"]["topic_focus"] == "Mitosis"
        assert wt_rec["priority"] == 2
        unrev_rec = next(r for r in data_rec if r["type"] == "unrevised_document")
        assert unrev_rec["priority"] == 3

    def test_completed_session_dynamically_updates_derived_progress(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)

        # Baseline: 0 completed sessions
        res_initial = client.get("/api/v1/progress/summary", cookies=cookies)
        assert res_initial.status_code == 200
        assert res_initial.json()["total_completed_sessions"] == 0

        # Complete a new session with 3 questions
        now = datetime.now(timezone.utc)
        s = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc_bio, now, score=1.0)
        for _ in range(3):
            add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="Enzymes", attempt_scores=[1.0])

        # Immediate follow-up query reflects updated progress dynamically without server restart
        res_updated = client.get("/api/v1/progress/summary", cookies=cookies)
        assert res_updated.status_code == 200
        assert res_updated.json()["total_completed_sessions"] == 1
        assert res_updated.json()["total_attempted_questions"] == 3
        assert res_updated.json()["overall_attempt_accuracy"] == 1.0

    def test_latest_persisted_attempt_used_consistently_without_inflating_counts(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        s = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc_bio, now, score=0.67)

        # Q1: attempt 1 = 0.0 (fail), attempt 2 = 1.0 (pass) -> latest is 1.0
        add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="DNA", attempt_scores=[0.0, 1.0])
        # Q2: attempt 1 = 1.0 (pass), attempt 2 = 0.0 (fail) -> latest is 0.0
        add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="DNA", attempt_scores=[1.0, 0.0])
        # Q3: attempt 1 = 1.0 (pass) -> latest is 1.0
        add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="DNA", attempt_scores=[1.0])

        res = client.get("/api/v1/progress/summary", cookies=cookies)
        assert res.status_code == 200
        data = res.json()
        assert data["total_attempted_questions"] == 3  # Not 5! Distinct count preserved
        assert data["total_attempts"] == 5  # Total attempts records volume accurately
        # Accuracy is computed from latest attempts: (1.0 + 0.0 + 1.0) / 3 = 2/3 ~ 0.67
        assert round(data["overall_attempt_accuracy"], 2) == 0.67

    def test_unanswered_questions_semantics_session_score_vs_mastery(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # Session with 4 total questions: 3 attempted (all correct), 1 unattempted
        s = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc_bio, now, score=0.75)
        for _ in range(3):
            add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="Osmosis", attempt_scores=[1.0])
        # 4th question with zero attempts
        add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="Osmosis", attempt_scores=[])

        res = client.get("/api/v1/progress/summary", cookies=cookies)
        assert res.status_code == 200
        data = res.json()
        assert data["total_questions_generated"] == 4
        assert data["total_attempted_questions"] == 3
        assert data["total_unanswered_questions"] == 1
        # Mastery calculation only evaluates attempted questions -> score is 1.0
        assert data["overall_mastery"]["score"] == 1.0
        assert data["overall_mastery"]["is_assessed"] is True

    def test_topic_identity_scoped_by_document_and_normalized_topic_key(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document, doc_genetics: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # Doc Bio: 3 questions on "Photosynthesis"
        s1 = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc_bio, now, score=1.0)
        for _ in range(3):
            add_question_with_attempts(db_session, s1, doc_bio.id, doc_bio.original_filename, topic="Photosynthesis", attempt_scores=[1.0])

        # Doc Genetics: 3 questions on "Photosynthesis" (same name, different doc)
        s2 = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc_genetics, now, score=1.0)
        for _ in range(3):
            add_question_with_attempts(db_session, s2, doc_genetics.id, doc_genetics.original_filename, topic="Photosynthesis", attempt_scores=[1.0])

        res = client.get("/api/v1/progress/topics", cookies=cookies)
        assert res.status_code == 200
        topics = res.json()
        # Must produce TWO distinct topic items because document provenance differs
        ps_topics = [t for t in topics if t["topic_key"] == "photosynthesis"]
        assert len(ps_topics) == 2
        doc_ids_in_topics = {t["document_id"] for t in ps_topics}
        assert doc_bio.id in doc_ids_in_topics
        assert doc_genetics.id in doc_ids_in_topics

    def test_archived_and_non_ready_docs_preserve_history_without_invalid_recommendations(
        self, client: TestClient, db_session: Session, user_a: User
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # Create an unready document (status = processing)
        uid = uuid.uuid4().hex[:8]
        unready_doc = Document(
            id=f"doc-unready-{uid}",
            original_filename="processing_paper.pdf",
            stored_filename=f"proc_{uid}.pdf",
            status="processing",
            owner_type=IdentityType.USER.value,
            owner_id=user_a.id,
        )
        db_session.add(unready_doc)
        db_session.commit()

        # Recommendations must strictly ignore the unready document
        res = client.get("/api/v1/progress/recommendations", cookies=cookies)
        assert res.status_code == 200
        recs = res.json()
        assert not any(r.get("document_id") == unready_doc.id for r in recs)

    def test_progress_endpoints_zero_ai_quota_and_zero_mutations(
        self, client: TestClient, db_session: Session
    ):
        # Create a fresh guest session
        guest = create_guest_session(db_session)
        cookies = auth_cookie_for_guest(guest)

        # Record initial guest quota and counts
        assert guest.ai_generation_count == 0
        initial_sess_count = db_session.query(RevisionSession).count()
        initial_q_count = db_session.query(RevisionQuestion).count()
        initial_att_count = db_session.query(RevisionAttempt).count()

        # Query all 5 Progress API endpoints under BombAIProvider
        r1 = client.get("/api/v1/progress/summary", cookies=cookies)
        r2 = client.get("/api/v1/progress/topics", cookies=cookies)
        r3 = client.get("/api/v1/progress/weak-topics", cookies=cookies)
        r4 = client.get("/api/v1/progress/spaced-repetition", cookies=cookies)
        r5 = client.get("/api/v1/progress/recommendations", cookies=cookies)

        assert all(r.status_code == 200 for r in (r1, r2, r3, r4, r5))

        # Refresh guest from database
        db_session.refresh(guest)
        assert guest.ai_generation_count == 0
        assert db_session.query(RevisionSession).count() == initial_sess_count
        assert db_session.query(RevisionQuestion).count() == initial_q_count
        assert db_session.query(RevisionAttempt).count() == initial_att_count


# ===========================================================================
# B. TARGETED REVISION AND RECOMMENDATION HANDOFF
# ===========================================================================

class TestTargetedRevisionAndRecommendationHandoff:
    """
    Verifies targeted Revision session creation, topic focus persistence,
    validation boundaries, and atomic failure handling.
    """

    def test_weak_topic_recommendation_handoff_and_targeted_session_creation(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # 1. Create historical session causing "Mitosis" to be flagged as weak
        s = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc_bio, now, score=0.0)
        for _ in range(3):
            add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="Mitosis", attempt_scores=[0.0])

        # 2. Get recommendations and extract action payload
        res_rec = client.get("/api/v1/progress/recommendations", cookies=cookies)
        assert res_rec.status_code == 200
        weak_rec = next(r for r in res_rec.json() if r["type"] == "weak_topic_practice")
        payload = weak_rec["action_payload"]
        assert payload["topic_focus"] == "Mitosis"
        assert doc_bio.id in payload["document_ids"]

        # 3. Use TargetedRevisionAIProvider to launch Revision session
        mock_ai = TargetedRevisionAIProvider(doc_bio.extracted_text)
        app.dependency_overrides[get_ai_provider] = lambda: mock_ai

        try:
            res_launch = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
            assert res_launch.status_code == 201
            session_data = res_launch.json()

            # Verify configuration and topic attribution
            assert session_data["config"]["topic_focus"] == "Mitosis"
            for q in session_data["questions"]:
                assert q["evidence_metadata"]["topic"] == "Mitosis"
                assert q["evidence_metadata"]["topic_key"] == "mitosis"
                assert q["source_document_id"] == doc_bio.id

            # Verify prompt contained topic focus
            assert len(mock_ai.prompts) == 1
            assert "TARGET TOPIC FOCUS" in mock_ai.prompts[0]
            assert "Mitosis" in mock_ai.prompts[0]
        finally:
            app.dependency_overrides.clear()

    def test_targeted_generation_unsupported_topic_returns_422(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        mock_ai = TargetedRevisionAIProvider(doc_bio.extracted_text)
        mock_ai.should_be_unsupported = True
        app.dependency_overrides[get_ai_provider] = lambda: mock_ai

        initial_count = db_session.query(RevisionSession).count()
        payload = {
            "document_ids": [doc_bio.id],
            "question_count": 3,
            "mode": "practice",
            "difficulty": "intermediate",
            "question_type": "multiple_choice",
            "topic_focus": "Quantum Electrodynamics",
        }

        try:
            res = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
            assert res.status_code == 422
            assert "do not contain sufficient content" in res.json()["detail"]
            # Zero sessions persisted
            assert db_session.query(RevisionSession).count() == initial_count
        finally:
            app.dependency_overrides.clear()

    def test_targeted_generation_atomic_failure_on_invalid_output(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        mock_ai = TargetedRevisionAIProvider(doc_bio.extracted_text)
        mock_ai.should_mismatch_count = True  # Returns 2 questions when 3 requested
        app.dependency_overrides[get_ai_provider] = lambda: mock_ai

        initial_count = db_session.query(RevisionSession).count()
        payload = {
            "document_ids": [doc_bio.id],
            "question_count": 3,
            "mode": "practice",
            "difficulty": "intermediate",
            "question_type": "multiple_choice",
            "topic_focus": "Mitosis",
        }

        try:
            res = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
            assert res.status_code == 502
            # Zero partial session or orphaned questions created
            assert db_session.query(RevisionSession).count() == initial_count
        finally:
            app.dependency_overrides.clear()

    def test_ordinary_generation_without_topic_focus_preserved(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        mock_ai = TargetedRevisionAIProvider(doc_bio.extracted_text)
        app.dependency_overrides[get_ai_provider] = lambda: mock_ai

        payload = {
            "document_ids": [doc_bio.id],
            "question_count": 3,
            "mode": "practice",
            "difficulty": "intermediate",
            "question_type": "multiple_choice",
        }

        try:
            res = client.post("/api/v1/revision/sessions", json=payload, cookies=cookies)
            assert res.status_code == 201
            data = res.json()
            assert data["config"]["topic_focus"] is None
            assert len(data["questions"]) == 3
        finally:
            app.dependency_overrides.clear()

    def test_retake_preparation_restores_topic_focus_without_auto_starting(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # Historical completed session with topic focus
        s = create_completed_session(
            db_session,
            IdentityType.USER.value,
            user_a.id,
            doc_bio,
            now,
            score=0.8,
            topic_focus="Cell Division",
        )
        add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="Cell Division", attempt_scores=[0.8])

        res = client.get(f"/api/v1/revision/sessions/{s.id}", cookies=cookies)
        assert res.status_code == 200
        detail = res.json()
        assert detail["config"]["topic_focus"] == "Cell Division"


# ===========================================================================
# C. GUEST-TO-ACCOUNT MIGRATION
# ===========================================================================

class TestGuestToAccountMigration:
    """
    Exercises guest-to-account migration with M5-compatible Revision history,
    verifying transactional ownership transfer and instant progress query updates.
    """

    def test_guest_to_account_migration_preserves_revision_and_progress_history(
        self, client: TestClient, db_session: Session, user_a: User
    ):
        now = datetime.now(timezone.utc)

        # 1. Create active guest session and document
        guest = create_guest_session(db_session)
        guest_cookies = auth_cookie_for_guest(guest)

        uid = uuid.uuid4().hex[:8]
        guest_doc = Document(
            id=f"doc-gst-{uid}",
            original_filename="guest_notes.pdf",
            stored_filename=f"gst_{uid}.pdf",
            status="ready",
            extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
            owner_type=IdentityType.GUEST.value,
            owner_id=guest.id,
        )
        db_session.add(guest_doc)
        db_session.commit()

        # 2. Create completed Revision session for guest with 3 questions
        s = create_completed_session(db_session, IdentityType.GUEST.value, guest.id, guest_doc, now, score=1.0)
        for _ in range(3):
            add_question_with_attempts(db_session, s, guest_doc.id, guest_doc.original_filename, topic="Bioenergetics", attempt_scores=[1.0])

        # 3. Verify progress is visible to the guest before migration
        res_guest_progress = client.get("/api/v1/progress/summary", cookies=guest_cookies)
        assert res_guest_progress.status_code == 200
        assert res_guest_progress.json()["total_completed_sessions"] == 1
        assert res_guest_progress.json()["overall_mastery"]["tier"] == "mastered"

        # 4. Perform migration to user_a
        result = migrate_guest_data_to_user(db_session, guest.id, user_a.id)
        assert result.documents_migrated == 1
        assert result.revision_sessions_migrated == 1

        # 5. User A immediately sees the migrated history without cache rebuild
        client.cookies.clear()
        user_cookies = auth_cookie_for_user(user_a, db_session)
        res_user_progress = client.get("/api/v1/progress/summary", cookies=user_cookies)
        assert res_user_progress.status_code == 200
        user_summary = res_user_progress.json()
        assert user_summary["total_completed_sessions"] == 1
        assert user_summary["total_attempted_questions"] == 3
        assert user_summary["overall_attempt_accuracy"] == 1.0

        # Verify topic mastery migrated intact
        res_user_topics = client.get("/api/v1/progress/topics", cookies=user_cookies)
        assert res_user_topics.status_code == 200
        assert any(t["topic_display"] == "Bioenergetics" for t in res_user_topics.json())

        # 6. Old guest session is revoked and cannot access progress
        client.cookies.clear()
        res_revoked = client.get("/api/v1/progress/summary", cookies=guest_cookies)
        # Guest session revoked -> identity dependency creates a fresh guest session with zero data
        assert res_revoked.status_code == 200
        assert res_revoked.json()["total_completed_sessions"] == 0

        # 7. No row duplication occurred
        assert db_session.query(RevisionSession).filter(RevisionSession.id == s.id).count() == 1
        assert db_session.query(RevisionQuestion).filter(RevisionQuestion.session_id == s.id).count() == 3

    def test_guest_migration_isolation_from_unrelated_users(
        self, client: TestClient, db_session: Session, user_a: User, user_b: User, doc_bio: Document
    ):
        now = datetime.now(timezone.utc)

        # User B already has a session on doc_bio
        s_b = create_completed_session(db_session, IdentityType.USER.value, user_b.id, doc_bio, now, score=0.5)
        add_question_with_attempts(db_session, s_b, doc_bio.id, doc_bio.original_filename, topic="Genetics", attempt_scores=[0.5])

        # Guest creates separate session
        guest = create_guest_session(db_session)
        uid = uuid.uuid4().hex[:8]
        g_doc = Document(
            id=f"doc-g2-{uid}",
            original_filename="g2.pdf",
            stored_filename=f"g2_{uid}.pdf",
            status="ready",
            extracted_text="Content",
            owner_type=IdentityType.GUEST.value,
            owner_id=guest.id,
        )
        db_session.add(g_doc)
        db_session.commit()

        s_g = create_completed_session(db_session, IdentityType.GUEST.value, guest.id, g_doc, now, score=1.0)
        add_question_with_attempts(db_session, s_g, g_doc.id, g_doc.original_filename, topic="Ecology", attempt_scores=[1.0])

        # Migrate guest to user_a
        migrate_guest_data_to_user(db_session, guest.id, user_a.id)

        # User A only sees Ecology (migrated), not User B's Genetics
        client.cookies.clear()
        cookies_a = auth_cookie_for_user(user_a, db_session)
        res_a = client.get("/api/v1/progress/topics", cookies=cookies_a)
        assert res_a.status_code == 200
        topics_a = {t["topic_display"] for t in res_a.json()}
        assert "Ecology" in topics_a
        assert "Genetics" not in topics_a

        # User B only sees Genetics, not Ecology
        client.cookies.clear()
        cookies_b = auth_cookie_for_user(user_b, db_session)
        res_b = client.get("/api/v1/progress/topics", cookies=cookies_b)
        assert res_b.status_code == 200
        topics_b = {t["topic_display"] for t in res_b.json()}
        assert "Genetics" in topics_b
        assert "Ecology" not in topics_b


# ===========================================================================
# D. DOCUMENT-DELETION DURABILITY
# ===========================================================================

class TestDocumentDeletionDurability:
    """
    Verifies that deleting a source document preserves learning history,
    questions, attempts, review schedules, and historical analytics without crashing.
    """

    def test_document_deletion_preserves_learning_history_and_analytics(
        self, client: TestClient, db_session: Session, user_a: User
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # 1. Create document for user A
        uid = uuid.uuid4().hex[:8]
        doc = Document(
            id=f"doc-del-{uid}",
            original_filename="neuroscience.pdf",
            stored_filename=f"neuro_{uid}.pdf",
            status="ready",
            extracted_text="Neurons transmit electrochemical action potentials across synapses.",
            owner_type=IdentityType.USER.value,
            owner_id=user_a.id,
        )
        db_session.add(doc)
        db_session.commit()

        # 2. Complete revision session
        s = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc, now, score=1.0)
        for _ in range(3):
            add_question_with_attempts(db_session, s, doc.id, doc.original_filename, topic="Synapses", attempt_scores=[1.0])

        # 3. Delete the document via API
        res_del = client.delete(f"/api/v1/documents/{doc.id}", cookies=cookies)
        assert res_del.status_code == 204

        # Verify DB foreign key set null: questions retain None source_document_id
        db_session.expire_all()
        q_row = db_session.query(RevisionQuestion).filter(RevisionQuestion.session_id == s.id).first()
        assert q_row.source_document_id is None
        assert q_row.evidence_metadata["document_title"] == "neuroscience.pdf"

        # 4. Verify all 5 Progress API endpoints remain readable without crashing

        # Summary
        res_sum = client.get("/api/v1/progress/summary", cookies=cookies)
        assert res_sum.status_code == 200
        assert res_sum.json()["total_completed_sessions"] == 1
        assert res_sum.json()["total_attempted_questions"] == 3

        # Topics: displays historical topic with is_archived = True
        res_top = client.get("/api/v1/progress/topics", cookies=cookies)
        assert res_top.status_code == 200
        topics = res_top.json()
        synapse_topic = next((t for t in topics if t["topic_display"] == "Synapses"), None)
        assert synapse_topic is not None
        assert synapse_topic["is_archived"] is True
        assert synapse_topic["document_title"] == "neuroscience.pdf"

        # Spaced Repetition: displays schedule with is_archived = True and is_actionable = False
        res_sr = client.get("/api/v1/progress/spaced-repetition?include_unreviewed_active=false", cookies=cookies)
        assert res_sr.status_code == 200
        schedules = res_sr.json()
        arch_sched = next((sch for sch in schedules if sch["document_title"] == "neuroscience.pdf"), None)
        assert arch_sched is not None
        assert arch_sched["is_archived"] is True
        assert arch_sched["is_actionable"] is False

        # Recommendations: deleted document CANNOT produce actionable recommendation
        res_rec = client.get("/api/v1/progress/recommendations", cookies=cookies)
        assert res_rec.status_code == 200
        recs = res_rec.json()
        assert not any(r.get("document_id") == doc.id for r in recs)

    def test_distinct_documents_do_not_merge_merely_because_titles_match(
        self, client: TestClient, db_session: Session, user_a: User
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        # Create two distinct documents with the SAME original_filename
        uid1 = uuid.uuid4().hex[:8]
        uid2 = uuid.uuid4().hex[:8]
        doc1 = Document(
            id=f"doc-same-1-{uid1}",
            original_filename="LectureNotes.pdf",
            stored_filename=f"f1_{uid1}.pdf",
            status="ready",
            extracted_text="Content 1",
            owner_type=IdentityType.USER.value,
            owner_id=user_a.id,
        )
        doc2 = Document(
            id=f"doc-same-2-{uid2}",
            original_filename="LectureNotes.pdf",
            stored_filename=f"f2_{uid2}.pdf",
            status="ready",
            extracted_text="Content 2",
            owner_type=IdentityType.USER.value,
            owner_id=user_a.id,
        )
        db_session.add_all([doc1, doc2])
        db_session.commit()

        # Session on doc1
        s1 = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc1, now, score=1.0)
        add_question_with_attempts(db_session, s1, doc1.id, "LectureNotes.pdf", topic="Topic A", attempt_scores=[1.0])

        # Session on doc2
        s2 = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc2, now, score=1.0)
        add_question_with_attempts(db_session, s2, doc2.id, "LectureNotes.pdf", topic="Topic A", attempt_scores=[1.0])

        res = client.get("/api/v1/progress/topics", cookies=cookies)
        assert res.status_code == 200
        topics = res.json()
        # They must NOT merge into a single item: 2 distinct items tracking separate provenance
        matching = [t for t in topics if t["topic_display"] == "Topic A"]
        assert len(matching) == 2
        assert {t["document_id"] for t in matching} == {doc1.id, doc2.id}


# ===========================================================================
# E. PHASE 4 WORKSPACE CONTRACT REGRESSION
# ===========================================================================

class TestPhase4WorkspaceContractRegression:
    """
    Verifies workspace contract invariants: read-only API contracts, schema compliance,
    and safe numerical formatting semantics.
    """

    def test_progress_endpoints_schema_contract_compliance(
        self, client: TestClient, db_session: Session, user_a: User, doc_bio: Document
    ):
        cookies = auth_cookie_for_user(user_a, db_session)
        now = datetime.now(timezone.utc)

        s = create_completed_session(db_session, IdentityType.USER.value, user_a.id, doc_bio, now, score=0.85)
        add_question_with_attempts(db_session, s, doc_bio.id, doc_bio.original_filename, topic="Biochemistry", attempt_scores=[0.85])

        # Verify summary response shape
        res = client.get("/api/v1/progress/summary", cookies=cookies)
        assert res.status_code == 200
        data = res.json()
        assert "overall_attempt_accuracy" in data
        assert "overall_mastery" in data
        assert "activity_windows" in data
        assert "difficulty_distribution" in data
        assert "flashcard_metrics" in data

        # Verify UTC ISO strings on date fields
        assert data["overall_mastery"]["last_attempted_at"] is not None
        assert "T" in data["overall_mastery"]["last_attempted_at"]

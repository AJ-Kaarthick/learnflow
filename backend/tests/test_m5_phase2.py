import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Document,
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    User,
)
from app.db.database import SessionLocal
from app.main import app  # Ensures startup migrations run on test DB
from app.schemas.identity import Identity, IdentityType
from app.services.spaced_repetition_service import (
    DocumentScheduleItem,
    ReviewEvent,
    calculate_schedule_for_events,
    get_document_schedule,
    get_interval_for_streak,
    get_review_schedules,
)
from app.services.weak_topic_service import (
    WeakTopicItem,
    calculate_struggle_index,
    detect_weak_topics,
    detect_weak_topics_for_document,
)


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
def test_user(db_session: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=f"user-p2-{uid}",
        email=f"user-p2-{uid}@example.com",
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
        id=f"other-p2-{uid}",
        email=f"other-p2-{uid}@example.com",
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
        id=f"doc-p2-{uid}",
        original_filename="biology_101.pdf",
        stored_filename=f"bio_{uid}.pdf",
        status="ready",
        extracted_text="Mitochondria generate cellular ATP via aerobic respiration.",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture()
def other_document(db_session: Session, test_user: User) -> Document:
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=f"doc-other-{uid}",
        original_filename="chemistry_101.pdf",
        stored_filename=f"chem_{uid}.pdf",
        status="ready",
        extracted_text="Atoms form molecules via covalent bonds.",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def create_session(
    db: Session,
    user: User,
    completed_at: Optional[datetime],
    status: str = "completed",
    title: str = "Revision Session",
) -> RevisionSession:
    sess = RevisionSession(
        id=f"sess-{uuid.uuid4().hex[:8]}",
        title=title,
        owner_type=IdentityType.USER.value,
        owner_id=user.id,
        status=status,
        completed_at=completed_at,
    )
    db.add(sess)
    db.flush()
    return sess


def add_question(
    db: Session,
    session: RevisionSession,
    position: int,
    doc_id: Optional[str],
    doc_title: str,
    topic: Optional[str] = None,
    attempts: Optional[list[tuple[float, bool, datetime]]] = None,
) -> RevisionQuestion:
    meta = {
        "source_document_id": doc_id,
        "document_title": doc_title,
    }
    if topic is not None:
        meta["topic"] = topic
        meta["topic_key"] = topic.strip().casefold()

    q = RevisionQuestion(
        id=f"q-{uuid.uuid4().hex[:8]}",
        session_id=session.id,
        position=position,
        question_text=f"Question {position} text?",
        correct_answer="A",
        source_document_id=doc_id,
        evidence_snippet="Sample evidence quote.",
        evidence_metadata=meta,
    )
    db.add(q)
    db.flush()

    if attempts:
        for idx, (score, is_correct, ts) in enumerate(attempts, start=1):
            att = RevisionAttempt(
                id=f"att-{uuid.uuid4().hex[:8]}",
                session_id=session.id,
                question_id=q.id,
                attempt_number=idx,
                submitted_answer="A" if is_correct else "B",
                is_correct=is_correct,
                score=score,
                created_at=ts,
            )
            db.add(att)
        db.flush()

    return q


# ===========================================================================
# Goal A: Weak-Topic Detection Tests (16 tests)
# ===========================================================================

def test_weak_topic_fewer_than_3_attempted_never_qualifies(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    1. Fewer than 3 distinct attempted questions never qualifies as weak,
       even if all answers are incorrect with 0.0 score.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # Only 2 distinct questions
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Cell Cycle", attempts=[(0.0, False, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, topic="Cell Cycle", attempts=[(0.0, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert weak_topics == []


def test_weak_topic_exactly_3_attempted_is_eligible(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    2. Exactly 3 distinct attempted questions is eligible to be detected as weak.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    for i in range(1, 4):
        add_question(
            db_session,
            sess,
            i,
            test_document.id,
            test_document.original_filename,
            topic="Cell Cycle",
            attempts=[(0.40, False, now)],
        )
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 1
    assert weak_topics[0].topic_key == "cell cycle"
    assert weak_topics[0].distinct_attempted_questions == 3
    assert weak_topics[0].mastery_score < 0.60


def test_weak_topic_mastery_just_below_60_qualifies(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    3. Mastery just below 0.60 (e.g. 0.59) qualifies even when all questions are marked correct.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    for i in range(1, 4):
        add_question(
            db_session,
            sess,
            i,
            test_document.id,
            test_document.original_filename,
            topic="Genetics",
            attempts=[(0.59, True, now)],
        )
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 1
    assert weak_topics[0].topic_key == "genetics"
    assert weak_topics[0].mastery_score == 0.59
    assert weak_topics[0].incorrect_ratio == 0.0


def test_weak_topic_mastery_exactly_60_does_not_qualify_through_score_alone(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    4. Mastery exactly 0.60 does not qualify through the score condition alone
       when incorrect ratio is not > 50%.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    for i in range(1, 4):
        add_question(
            db_session,
            sess,
            i,
            test_document.id,
            test_document.original_filename,
            topic="Genetics",
            attempts=[(0.60, True, now)],
        )
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert weak_topics == []


def test_weak_topic_more_than_50_percent_incorrect_qualifies(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    5. More than 50% incorrect latest attempts qualifies even when mastery score is >= 0.60.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # Q1 correct (0.90), Q2 incorrect (0.70), Q3 incorrect (0.70)
    # Average score = 0.7667 >= 0.60. Incorrect ratio = 2/3 = 66.7% > 50%
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Ecology", attempts=[(0.90, True, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, topic="Ecology", attempts=[(0.70, False, now)])
    add_question(db_session, sess, 3, test_document.id, test_document.original_filename, topic="Ecology", attempts=[(0.70, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 1
    assert weak_topics[0].topic_key == "ecology"
    assert weak_topics[0].mastery_score >= 0.60
    assert weak_topics[0].incorrect_questions_count == 2
    assert weak_topics[0].incorrect_ratio > 0.50


def test_weak_topic_exactly_50_percent_incorrect_does_not_qualify_when_mastery_ge_60(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    6. Exactly 50% incorrect does not qualify through the incorrect-ratio condition alone
       when mastery is at least 0.60.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # 4 questions: 2 correct (1.0), 2 incorrect (0.70) -> Average score = 0.85 >= 0.60
    # Incorrect ratio = 2/4 = 50% exactly (not strictly > 50%)
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Evolution", attempts=[(1.0, True, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, topic="Evolution", attempts=[(1.0, True, now)])
    add_question(db_session, sess, 3, test_document.id, test_document.original_filename, topic="Evolution", attempts=[(0.70, False, now)])
    add_question(db_session, sess, 4, test_document.id, test_document.original_filename, topic="Evolution", attempts=[(0.70, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert weak_topics == []


def test_weak_topic_retries_do_not_inflate_distinct_question_count(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    7. Retries do not inflate the distinct-question count (2 questions retried multiple times < 3).
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # Q1 with 3 attempts, Q2 with 2 attempts (TotalAttempts=5, but only 2 distinct questions)
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Proteins", attempts=[(0.0, False, now), (0.1, False, now), (0.2, False, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, topic="Proteins", attempts=[(0.0, False, now), (0.1, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert weak_topics == []


def test_weak_topic_latest_attempt_determines_correctness(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    8. The latest attempt for each question determines correctness evidence.
       Earlier failed attempts that were subsequently mastered do not cause weakness.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # Q1 and Q2 initially failed, but retried successfully
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Lipids", attempts=[(0.0, False, now), (0.90, True, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, topic="Lipids", attempts=[(0.0, False, now), (0.90, True, now)])
    # Q3 succeeded then retried with lower score
    add_question(db_session, sess, 3, test_document.id, test_document.original_filename, topic="Lipids", attempts=[(0.80, True, now), (0.60, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    # Latest: Q1 True, Q2 True, Q3 False -> 1/3 incorrect (33% <= 50%), mastery = 0.80 >= 0.60
    assert weak_topics == []


def test_weak_topic_retries_contribute_to_total_attempts_and_struggle_index(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    9. Retries contribute to TotalAttempts and the struggle-index formula without inflating distinct questions.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # 3 distinct questions, total 6 attempts
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Enzymes", attempts=[(0.2, False, now), (0.3, False, now), (0.40, False, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, topic="Enzymes", attempts=[(0.2, False, now), (0.40, False, now)])
    add_question(db_session, sess, 3, test_document.id, test_document.original_filename, topic="Enzymes", attempts=[(0.40, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 1
    item = weak_topics[0]
    assert item.distinct_attempted_questions == 3
    assert item.total_attempts == 6
    assert item.mastery_score == 0.40
    expected_struggle = round((1.0 - 0.40) * math.log(1.0 + 6), 4)
    assert math.isclose(item.struggle_index, expected_struggle, abs_tol=1e-4)


def test_weak_topic_two_documents_same_topic_remain_separate(
    db_session: Session,
    test_user: User,
    test_document: Document,
    other_document: Document,
):
    """
    10. Two documents containing the same topic remain separate groups.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # 3 questions for test_document on "Bioenergetics"
    for i in range(1, 4):
        add_question(db_session, sess, i, test_document.id, test_document.original_filename, topic="Bioenergetics", attempts=[(0.40, False, now)])

    # 3 questions for other_document on "Bioenergetics"
    for i in range(4, 7):
        add_question(db_session, sess, i, other_document.id, other_document.original_filename, topic="Bioenergetics", attempts=[(0.30, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 2
    doc_ids = {wt.document_id for wt in weak_topics}
    assert doc_ids == {test_document.id, other_document.id}


def test_weak_topic_case_whitespace_normalization_groups_correctly(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    11. Case/whitespace-normalized topic keys group correctly within the same document.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Cell Division", attempts=[(0.40, False, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, topic="  cell division", attempts=[(0.40, False, now)])
    add_question(db_session, sess, 3, test_document.id, test_document.original_filename, topic="CELL DIVISION ", attempts=[(0.40, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 1
    assert weak_topics[0].topic_key == "cell division"
    assert weak_topics[0].distinct_attempted_questions == 3


def test_weak_topic_legacy_questions_without_metadata_not_invented(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    12. Legacy questions without topic metadata do not acquire invented topics.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    for i in range(1, 4):
        # topic=None -> no topic metadata
        add_question(db_session, sess, i, test_document.id, test_document.original_filename, topic=None, attempts=[(0.20, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert weak_topics == []


def test_weak_topic_ignores_in_progress_and_foreign_sessions(
    db_session: Session,
    test_user: User,
    other_user: User,
    test_document: Document,
):
    """
    13. In-progress sessions and sessions owned by another identity do not affect results.
    """
    now = datetime.now(timezone.utc)

    # Completed session for test_user with only 2 questions
    sess_user = create_session(db_session, test_user, completed_at=now, status="completed")
    add_question(db_session, sess_user, 1, test_document.id, test_document.original_filename, topic="Photosynthesis", attempts=[(0.20, False, now)])
    add_question(db_session, sess_user, 2, test_document.id, test_document.original_filename, topic="Photosynthesis", attempts=[(0.20, False, now)])

    # In-progress session for test_user with 1 question (should be ignored)
    sess_in_prog = create_session(db_session, test_user, completed_at=None, status="in_progress")
    add_question(db_session, sess_in_prog, 1, test_document.id, test_document.original_filename, topic="Photosynthesis", attempts=[(0.20, False, now)])

    # Completed session for other_user with 1 question (should be ignored)
    sess_other = create_session(db_session, other_user, completed_at=now, status="completed")
    add_question(db_session, sess_other, 1, test_document.id, test_document.original_filename, topic="Photosynthesis", attempts=[(0.20, False, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    # Only 2 distinct questions from completed sessions owned by test_user -> does not qualify
    assert weak_topics == []


def test_weak_topic_archived_document_marked_non_actionable(
    db_session: Session,
    test_user: User,
):
    """
    14. Archived document snapshots preserve provenance and are marked non-actionable for downstream actions.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    deleted_doc_id = f"doc-del-{uuid.uuid4().hex[:8]}"
    deleted_doc_title = "Archived Syllabus Notes.pdf"

    for i in range(1, 4):
        add_question(
            db_session,
            sess,
            i,
            deleted_doc_id,
            deleted_doc_title,
            topic="Homeostasis",
            attempts=[(0.30, False, now)],
        )
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 1
    item = weak_topics[0]
    assert item.document_id == deleted_doc_id
    assert item.document_title == deleted_doc_title
    assert item.is_archived is True
    assert item.is_actionable is False


def test_weak_topic_struggle_index_calculation_matches_formula(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    15. Struggle-index calculation matches (1 - MasteryScore) * ln(1 + TotalAttempts).
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    for i in range(1, 4):
        add_question(
            db_session,
            sess,
            i,
            test_document.id,
            test_document.original_filename,
            topic="Neuroscience",
            attempts=[(0.50, False, now)],
        )
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 1
    item = weak_topics[0]
    expected = (1.0 - item.mastery_score) * math.log(1.0 + item.total_attempts)
    assert math.isclose(item.struggle_index, expected, abs_tol=1e-4)


def test_weak_topic_deterministic_ordering(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    16. Results are deterministic and correctly ordered by struggle index descending.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # Topic A: 3 attempts, score 0.50 -> struggle = 0.50 * ln(4) = 0.6931
    for i in range(1, 4):
        add_question(db_session, sess, i, test_document.id, test_document.original_filename, topic="Topic A", attempts=[(0.50, False, now)])

    # Topic B: 6 attempts, score 0.20 -> struggle = 0.80 * ln(7) = 1.5567
    for i in range(4, 7):
        add_question(db_session, sess, i, test_document.id, test_document.original_filename, topic="Topic B", attempts=[(0.20, False, now), (0.20, False, now)])

    # Topic C: 3 attempts, score 0.30 -> struggle = 0.70 * ln(4) = 0.9704
    for i in range(7, 10):
        add_question(db_session, sess, i, test_document.id, test_document.original_filename, topic="Topic C", attempts=[(0.30, False, now)])

    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    weak_topics = detect_weak_topics(db_session, identity, now=now)
    assert len(weak_topics) == 3
    # Expected ordering: Topic B (1.5567) > Topic C (0.9704) > Topic A (0.6931)
    assert [wt.topic_key for wt in weak_topics] == ["topic b", "topic c", "topic a"]


# ===========================================================================
# Goal B: Spaced-Repetition Scheduling Tests (17 tests)
# ===========================================================================

def test_sr_session_document_pair_contributes_one_event_despite_retries(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    1. A session/document pair contributes one event even when its questions have multiple attempts.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # 2 questions, each retried 3 times
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, attempts=[(0.5, False, now), (0.8, True, now), (1.0, True, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, attempts=[(0.6, False, now), (0.7, True, now), (0.8, True, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, test_document.id, now=now)
    assert sched is not None
    assert sched.has_history is True
    # 1 session -> 1 event -> streak 1
    assert sched.current_streak == 1
    # Average of latest: (1.0 + 0.8) / 2 = 0.90
    assert sched.latest_review_score == 0.90


def test_sr_document_in_session_associations_without_questions_gets_no_event(
    db_session: Session,
    test_user: User,
    test_document: Document,
    other_document: Document,
):
    """
    2. A document present in session associations but with no attributed questions gets no event.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # Associate both documents with the session
    db_session.add(RevisionSessionDocument(session_id=sess.id, document_id=test_document.id))
    db_session.add(RevisionSessionDocument(session_id=sess.id, document_id=other_document.id))
    db_session.flush()

    # Questions ONLY for test_document
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, attempts=[(0.90, True, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched_other = get_document_schedule(db_session, identity, other_document.id, now=now)
    assert sched_other is not None
    assert sched_other.has_history is False
    assert sched_other.latest_review_score is None


def test_sr_unanswered_questions_contribute_zero_and_remain_in_denominator(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    3. Unanswered questions contribute zero to the document event score and remain in its denominator.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # Q1 answered 1.0; Q2 unanswered (0.0) -> Event average score = (1.0 + 0.0) / 2 = 0.50
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, attempts=[(1.0, True, now)])
    add_question(db_session, sess, 2, test_document.id, test_document.original_filename, attempts=None)
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, test_document.id, now=now)
    assert sched is not None
    assert sched.has_history is True
    assert sched.latest_review_score == 0.50
    # Score 0.50 < 0.70 -> failure -> streak 0
    assert sched.current_streak == 0
    assert sched.interval_days == 1


def test_sr_answered_question_uses_latest_attempt_score(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    4. An answered question uses its latest attempt's score.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, attempts=[(0.20, False, now), (1.0, True, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, test_document.id, now=now)
    assert sched is not None
    assert sched.latest_review_score == 1.0
    assert sched.current_streak == 1


def test_sr_score_threshold_exact_70_succeeds_below_fails(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    5. A score exactly 0.70 succeeds; a score below 0.70 fails.
    """
    t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)

    # Event 1: score exactly 0.70 -> succeeds (streak 1)
    sess1 = create_session(db_session, test_user, completed_at=t1)
    add_question(db_session, sess1, 1, test_document.id, test_document.original_filename, attempts=[(0.70, True, t1)])

    # Event 2: score 0.6999 -> fails (resets streak to 0)
    sess2 = create_session(db_session, test_user, completed_at=t2)
    add_question(db_session, sess2, 1, test_document.id, test_document.original_filename, attempts=[(0.6999, False, t2)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, test_document.id, now=t2)
    assert sched is not None
    assert sched.latest_review_score == 0.6999
    assert sched.current_streak == 0
    assert sched.interval_days == 1


def test_sr_streak_transitions_produce_exact_intervals(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    6. Success streak transitions produce the exact 1, 3, 7, 14, 30, 60 day intervals.
    """
    base_time = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    expected_intervals = [1, 3, 7, 14, 30, 60, 60]

    for i in range(1, 8):
        t = base_time + timedelta(days=i)
        sess = create_session(db_session, test_user, completed_at=t)
        add_question(db_session, sess, 1, test_document.id, test_document.original_filename, attempts=[(0.85, True, t)])
        db_session.commit()

        identity = Identity(type=IdentityType.USER, id=test_user.id)
        sched = get_document_schedule(db_session, identity, test_document.id, now=t)
        assert sched is not None
        assert sched.current_streak == i
        expected_interval = expected_intervals[i - 1]
        assert sched.interval_days == expected_interval
        assert sched.next_review_due == t + timedelta(days=expected_interval)


def test_sr_failure_resets_streak_to_zero_and_sets_interval_to_one_day(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    7. A failure resets the streak to 0 and sets the interval to one day.
       The next success starts a new streak at 1.
    """
    t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 3, 12, 0, tzinfo=timezone.utc)
    t4 = datetime(2026, 1, 4, 12, 0, tzinfo=timezone.utc)

    # Success streak reaches 2
    s1 = create_session(db_session, test_user, completed_at=t1)
    add_question(db_session, s1, 1, test_document.id, test_document.original_filename, attempts=[(0.80, True, t1)])
    s2 = create_session(db_session, test_user, completed_at=t2)
    add_question(db_session, s2, 1, test_document.id, test_document.original_filename, attempts=[(0.80, True, t2)])

    # Failure resets streak to 0, interval 1
    s3 = create_session(db_session, test_user, completed_at=t3)
    add_question(db_session, s3, 1, test_document.id, test_document.original_filename, attempts=[(0.50, False, t3)])

    db_session.commit()
    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched_fail = get_document_schedule(db_session, identity, test_document.id, now=t3)
    assert sched_fail is not None
    assert sched_fail.current_streak == 0
    assert sched_fail.interval_days == 1

    # Next success restarts streak at 1, interval 1
    s4 = create_session(db_session, test_user, completed_at=t4)
    add_question(db_session, s4, 1, test_document.id, test_document.original_filename, attempts=[(0.90, True, t4)])
    db_session.commit()

    sched_recover = get_document_schedule(db_session, identity, test_document.id, now=t4)
    assert sched_recover is not None
    assert sched_recover.current_streak == 1
    assert sched_recover.interval_days == 1


def test_sr_event_ordering_with_timestamp_tiebreaker(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    8. An event sequence is ordered deterministically using completion timestamp and session ID when timestamps tie.
    """
    tied_time = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    # sess_b with score 0.50 (fail)
    sess_b = RevisionSession(
        id="sess-b-tie",
        title="Session B",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="completed",
        completed_at=tied_time,
    )
    db_session.add(sess_b)
    db_session.flush()
    add_question(db_session, sess_b, 1, test_document.id, test_document.original_filename, attempts=[(0.50, False, tied_time)])

    # sess_a with score 1.0 (success)
    sess_a = RevisionSession(
        id="sess-a-tie",
        title="Session A",
        owner_type=IdentityType.USER.value,
        owner_id=test_user.id,
        status="completed",
        completed_at=tied_time,
    )
    db_session.add(sess_a)
    db_session.flush()
    add_question(db_session, sess_a, 1, test_document.id, test_document.original_filename, attempts=[(1.0, True, tied_time)])
    db_session.commit()

    # In ascending tiebreak, "sess-a-tie" precedes "sess-b-tie".
    # sess-a succeeds (streak 1), then sess-b fails (streak resets to 0).
    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, test_document.id, now=tied_time)
    assert sched is not None
    assert sched.current_streak == 0
    assert sched.latest_review_score == 0.50


def test_sr_retries_do_not_create_separate_events_or_advance_streak(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    9. Retries do not create separate review events or independently advance a streak.
    """
    now = datetime.now(timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)

    # 1 question retried 4 times
    add_question(
        db_session,
        sess,
        1,
        test_document.id,
        test_document.original_filename,
        attempts=[(0.8, True, now), (0.85, True, now), (0.9, True, now), (0.95, True, now)],
    )
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, test_document.id, now=now)
    assert sched is not None
    assert sched.current_streak == 1
    assert sched.interval_days == 1


def test_sr_next_review_due_and_is_due_against_injected_now(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    10. The calculated next-review date and is_due are correct for an injectable UTC now.
    """
    completed_time = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    sess = create_session(db_session, test_user, completed_at=completed_time)
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, attempts=[(0.80, True, completed_time)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    # Streak 1 -> interval 1 day -> due at 2026-03-02 10:00:00 UTC

    # 1 second before due -> not due
    before_due = datetime(2026, 3, 2, 9, 59, 59, tzinfo=timezone.utc)
    s_before = get_document_schedule(db_session, identity, test_document.id, now=before_due)
    assert s_before is not None
    assert s_before.is_due is False

    # Exact due time -> due
    exact_due = datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc)
    s_exact = get_document_schedule(db_session, identity, test_document.id, now=exact_due)
    assert s_exact is not None
    assert s_exact.is_due is True

    # After due -> due
    after_due = datetime(2026, 3, 3, 10, 0, 0, tzinfo=timezone.utc)
    s_after = get_document_schedule(db_session, identity, test_document.id, now=after_due)
    assert s_after is not None
    assert s_after.is_due is True


def test_sr_naive_and_aware_timestamps_normalized_consistently(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    11. Naive and timezone-aware timestamps are normalized consistently without error.
    """
    # Naive timestamp (no tzinfo)
    naive_completed = datetime(2026, 4, 1, 12, 0)
    sess = create_session(db_session, test_user, completed_at=naive_completed)
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, attempts=[(0.90, True, naive_completed)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    aware_now = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)
    sched = get_document_schedule(db_session, identity, test_document.id, now=aware_now)
    assert sched is not None
    assert sched.last_reviewed_at.tzinfo == timezone.utc
    assert sched.next_review_due.tzinfo == timezone.utc
    assert sched.is_due is True


def test_sr_deleted_doc_snapshot_and_legacy_title_fallback(
    db_session: Session,
    test_user: User,
):
    """
    12. Deleted-document snapshot IDs and legacy title fallback resolve consistently;
        unrelated document IDs do not merge simply because titles match.
    """
    t1 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    sess = create_session(db_session, test_user, completed_at=t1)

    # Deleted doc 1 with title "Cell Notes"
    add_question(db_session, sess, 1, "del-id-1", "Cell Notes", attempts=[(0.90, True, t1)])

    # Deleted doc 2 with same title "Cell Notes" but different ID
    add_question(db_session, sess, 2, "del-id-2", "Cell Notes", attempts=[(0.90, True, t1)])

    # Legacy doc with no ID, title "Legacy Cell Notes"
    add_question(db_session, sess, 3, None, "Legacy Cell Notes", attempts=[(0.90, True, t1)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    schedules = get_review_schedules(db_session, identity, now=t1, include_unreviewed_active=False)

    # del-id-1 and del-id-2 must remain separate items
    del_ids = {s.document_id for s in schedules}
    assert "del-id-1" in del_ids
    assert "del-id-2" in del_ids
    assert None in del_ids
    assert len(schedules) == 3


def test_sr_archived_documents_are_non_actionable(
    db_session: Session,
    test_user: User,
):
    """
    13. Archived documents retain derived historical state, but must not be marked actionable.
    """
    t = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    sess = create_session(db_session, test_user, completed_at=t)
    add_question(db_session, sess, 1, "deleted-doc-xyz", "Old Physics.pdf", attempts=[(0.90, True, t)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, "deleted-doc-xyz", now=t)
    assert sched is not None
    assert sched.is_archived is True
    assert sched.is_actionable is False
    assert sched.has_history is True
    assert sched.current_streak == 1


def test_sr_no_completed_review_history_explicit_no_history(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    14. No completed review history produces an explicit no-history result without an invented due-date anchor.
    """
    now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    identity = Identity(type=IdentityType.USER, id=test_user.id)

    sched = get_document_schedule(db_session, identity, test_document.id, now=now)
    assert sched is not None
    assert sched.has_history is False
    assert sched.latest_review_score is None
    assert sched.last_reviewed_at is None
    assert sched.current_streak == 0
    assert sched.interval_days is None
    assert sched.next_review_due is None
    assert sched.is_due is False
    assert sched.is_archived is False
    assert sched.is_actionable is True

    # Also verify pure calculate_schedule_for_events directly
    empty_sched = calculate_schedule_for_events([], test_document.id, test_document.original_filename, False, now=now)
    assert empty_sched.has_history is False
    assert empty_sched.next_review_due is None


def test_sr_ignores_in_progress_and_foreign_sessions(
    db_session: Session,
    test_user: User,
    other_user: User,
    test_document: Document,
):
    """
    15. In-progress sessions and sessions belonging to another identity are excluded.
    """
    now = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

    # In-progress session for test_user (should be excluded)
    sess_in_prog = create_session(db_session, test_user, completed_at=None, status="in_progress")
    add_question(db_session, sess_in_prog, 1, test_document.id, test_document.original_filename, attempts=[(1.0, True, now)])

    # Completed session for other_user (should be excluded)
    sess_other = create_session(db_session, other_user, completed_at=now, status="completed")
    add_question(db_session, sess_other, 1, test_document.id, test_document.original_filename, attempts=[(1.0, True, now)])
    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    sched = get_document_schedule(db_session, identity, test_document.id, now=now)
    assert sched is not None
    assert sched.has_history is False


def test_sr_no_database_mutations(
    db_session: Session,
    test_user: User,
    test_document: Document,
):
    """
    16. No database rows are mutated and no new database state is persisted.
    """
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    sess = create_session(db_session, test_user, completed_at=now)
    add_question(db_session, sess, 1, test_document.id, test_document.original_filename, topic="Ecology", attempts=[(0.40, False, now)])
    db_session.commit()

    sess_count_before = db_session.query(RevisionSession).count()
    q_count_before = db_session.query(RevisionQuestion).count()
    att_count_before = db_session.query(RevisionAttempt).count()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    _ = get_review_schedules(db_session, identity, now=now)
    _ = detect_weak_topics(db_session, identity, now=now)

    assert db_session.query(RevisionSession).count() == sess_count_before
    assert db_session.query(RevisionQuestion).count() == q_count_before
    assert db_session.query(RevisionAttempt).count() == att_count_before


def test_sr_deterministic_ordering(
    db_session: Session,
    test_user: User,
    test_document: Document,
    other_document: Document,
):
    """
    17. Results are deterministic and correctly ordered:
        active/actionable before archived, due before upcoming, earliest due first.
    """
    t_past = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    now = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)

    # Doc 1 (test_document): reviewed long ago (past interval) -> is_due = True
    s1 = create_session(db_session, test_user, completed_at=t_past)
    add_question(db_session, s1, 1, test_document.id, test_document.original_filename, attempts=[(0.80, True, t_past)])

    # Doc 2 (other_document): reviewed just now at t=now (interval 1 day) -> next due tomorrow -> is_due = False
    s2 = create_session(db_session, test_user, completed_at=now)
    add_question(db_session, s2, 1, other_document.id, other_document.original_filename, attempts=[(0.80, True, now)])

    db_session.commit()

    identity = Identity(type=IdentityType.USER, id=test_user.id)
    schedules = get_review_schedules(db_session, identity, now=now)

    # Expected: Due document (test_document) comes before upcoming document (other_document)
    assert len(schedules) >= 2
    assert schedules[0].document_id == test_document.id
    assert schedules[0].is_due is True
    assert schedules[1].document_id == other_document.id
    assert schedules[1].is_due is False

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Document, RevisionQuestion, RevisionSession
from app.schemas.identity import Identity
from app.services.mastery_service import (
    ensure_utc,
    get_completed_sessions_for_identity,
    resolve_document_info,
)

REVIEW_SUCCESS_THRESHOLD = 0.70

# Streak to review interval mapping in days
STREAK_INTERVAL_MAP = {
    1: 1,
    2: 3,
    3: 7,
    4: 14,
    5: 30,
}


def get_interval_for_streak(streak: int, is_success: bool) -> int:
    """
    Returns the review interval in days for a given success streak:
    - Failed review (score < 0.70): 1 day
    - First success (streak 1): 1 day
    - Second success (streak 2): 3 days
    - Third success (streak 3): 7 days
    - Fourth success (streak 4): 14 days
    - Fifth success (streak 5): 30 days
    - Sixth or later success (streak 6+): 60 days
    """
    if not is_success or streak <= 0:
        return 1
    return STREAK_INTERVAL_MAP.get(streak, 60)


@dataclass
class ReviewEvent:
    """
    Represents one document-level review event derived from a completed RevisionSession.
    """
    document_id: Optional[str]
    document_title: str
    is_archived: bool
    session_id: str
    completed_at: datetime
    score: float
    is_successful: bool


@dataclass
class DocumentScheduleItem:
    """
    Structured spaced-repetition schedule item for a document.
    """
    document_id: Optional[str]
    document_title: str
    is_archived: bool
    is_actionable: bool
    has_history: bool
    latest_review_score: Optional[float]
    last_reviewed_at: Optional[datetime]
    current_streak: int
    interval_days: Optional[int]
    next_review_due: Optional[datetime]
    is_due: bool


def calculate_schedule_for_events(
    events: list[ReviewEvent],
    document_id: Optional[str],
    document_title: str,
    is_archived: bool,
    now: Optional[datetime] = None,
) -> DocumentScheduleItem:
    """
    Computes streak, interval, due date, and is_due from a chronologically sorted list of ReviewEvents.
    If events is empty, returns an explicit no-history result without fabricating a due-date anchor.
    """
    ref_now = ensure_utc(now) or datetime.now(timezone.utc)
    is_actionable = not is_archived

    if not events:
        return DocumentScheduleItem(
            document_id=document_id,
            document_title=document_title,
            is_archived=is_archived,
            is_actionable=is_actionable,
            has_history=False,
            latest_review_score=None,
            last_reviewed_at=None,
            current_streak=0,
            interval_days=None,
            next_review_due=None,
            is_due=False,
        )

    # Sort events chronologically by (session.completed_at ASC, session.id ASC)
    sorted_events = sorted(
        events,
        key=lambda ev: (
            ensure_utc(ev.completed_at) or datetime.min.replace(tzinfo=timezone.utc),
            ev.session_id,
        ),
    )

    streak = 0
    interval = 1
    last_score: Optional[float] = None
    last_completed_at: Optional[datetime] = None

    for ev in sorted_events:
        is_success = ev.score >= REVIEW_SUCCESS_THRESHOLD
        if is_success:
            streak += 1
            interval = get_interval_for_streak(streak, True)
        else:
            streak = 0
            interval = get_interval_for_streak(0, False)

        last_score = ev.score
        last_completed_at = ensure_utc(ev.completed_at)

    assert last_completed_at is not None
    next_due = last_completed_at + timedelta(days=interval)
    is_due = ref_now >= next_due

    return DocumentScheduleItem(
        document_id=document_id,
        document_title=document_title,
        is_archived=is_archived,
        is_actionable=is_actionable,
        has_history=True,
        latest_review_score=round(last_score, 4) if last_score is not None else None,
        last_reviewed_at=last_completed_at,
        current_streak=streak,
        interval_days=interval,
        next_review_due=next_due,
        is_due=is_due,
    )


def get_review_schedules(
    db: Session,
    identity: Identity,
    now: Optional[datetime] = None,
    include_unreviewed_active: bool = True,
) -> list[DocumentScheduleItem]:
    """
    Derives spaced-repetition review schedules from completed RevisionSession history.

    - Excludes in-progress sessions and sessions of other identities.
    - Groups questions in each completed session by resolved source document.
    - Calculates average question score (unanswered count as 0.0).
    - Sorts events chronologically to compute streaks and due dates.
    - Preserves archived document history while marking archived entries non-actionable.
    - Deterministic output ordering: active actionable due first, earliest due date first.
    """
    sessions = get_completed_sessions_for_identity(db, identity)

    active_docs = (
        db.query(Document)
        .filter(
            Document.owner_type == identity.type.value,
            Document.owner_id == identity.id,
        )
        .all()
    )
    active_docs_by_id = {d.id: d for d in active_docs}

    # Map: doc_key -> list of ReviewEvent
    doc_events_map: dict[str, list[ReviewEvent]] = {}
    doc_meta_map: dict[str, tuple[Optional[str], str, bool]] = {}

    for s in sessions:
        if s.completed_at is None:
            continue
        completed_at = ensure_utc(s.completed_at)

        # Group session questions by resolved source-document identity
        session_doc_questions: dict[str, list[RevisionQuestion]] = {}
        for q in s.questions:
            doc_id, doc_title, is_archived = resolve_document_info(q, active_docs_by_id)
            doc_key = f"id:{doc_id}" if doc_id else f"title:{doc_title}"

            if doc_key not in doc_meta_map:
                doc_meta_map[doc_key] = (doc_id, doc_title, is_archived)

            if doc_key not in session_doc_questions:
                session_doc_questions[doc_key] = []
            session_doc_questions[doc_key].append(q)

        # Create one document-level review event per document represented in this session
        for doc_key, q_list in session_doc_questions.items():
            doc_id, doc_title, is_archived = doc_meta_map[doc_key]
            question_scores: list[float] = []

            for q in q_list:
                if q.attempts:
                    latest = max(q.attempts, key=lambda a: a.attempt_number)
                    question_scores.append(float(latest.score))
                else:
                    # Unanswered questions contribute zero and remain in the denominator
                    question_scores.append(0.0)

            avg_score = (
                round(sum(question_scores) / len(question_scores), 4)
                if question_scores
                else 0.0
            )
            is_success = avg_score >= REVIEW_SUCCESS_THRESHOLD

            event = ReviewEvent(
                document_id=doc_id,
                document_title=doc_title,
                is_archived=is_archived,
                session_id=s.id,
                completed_at=completed_at,
                score=avg_score,
                is_successful=is_success,
            )

            if doc_key not in doc_events_map:
                doc_events_map[doc_key] = []
            doc_events_map[doc_key].append(event)

    schedules: list[DocumentScheduleItem] = []

    # Calculate schedule for documents with review history
    for doc_key, events in doc_events_map.items():
        doc_id, doc_title, is_archived = doc_meta_map[doc_key]
        item = calculate_schedule_for_events(
            events=events,
            document_id=doc_id,
            document_title=doc_title,
            is_archived=is_archived,
            now=now,
        )
        schedules.append(item)

    # If requested, include active unreviewed documents with explicit no-history state
    if include_unreviewed_active:
        for active_doc in active_docs:
            doc_key = f"id:{active_doc.id}"
            if doc_key not in doc_events_map:
                item = calculate_schedule_for_events(
                    events=[],
                    document_id=active_doc.id,
                    document_title=active_doc.original_filename,
                    is_archived=False,
                    now=now,
                )
                schedules.append(item)

    # Deterministic sorting:
    # 1. Actionable/Active before archived (item.is_archived: False before True)
    # 2. Due reviews first (not item.is_due: False before True)
    # 3. Next review due timestamp (earliest due first; None at the end)
    # 4. Document title case-folded
    # 5. Document ID
    def _sort_key(item: DocumentScheduleItem):
        due_val = (
            ensure_utc(item.next_review_due)
            or datetime.max.replace(tzinfo=timezone.utc)
        )
        return (
            item.is_archived,
            not item.is_due,
            due_val,
            item.document_title.casefold(),
            item.document_id or "",
        )

    schedules.sort(key=lambda item: _sort_key(item))
    return schedules


def get_document_schedule(
    db: Session,
    identity: Identity,
    document_id: str,
    now: Optional[datetime] = None,
) -> Optional[DocumentScheduleItem]:
    """
    Returns the review schedule for a specific document ID.
    If the document exists but has no completed sessions, returns an explicit no-history result.
    If the document does not exist for this identity and has no history, returns None.
    """
    schedules = get_review_schedules(
        db,
        identity,
        now=now,
        include_unreviewed_active=True,
    )
    for s in schedules:
        if s.document_id == document_id:
            return s
    return None

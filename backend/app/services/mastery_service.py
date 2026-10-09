import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.db.models import Document, RevisionAttempt, RevisionQuestion, RevisionSession
from app.schemas.identity import Identity
from app.services.revision_service import clean_and_normalize_topic

# 14-day exponential decay half-life constant
HALF_LIFE_DAYS = 14.0
LAMBDA_DECAY = math.log(2) / HALF_LIFE_DAYS  # ~0.04951051289819625
MIN_QUESTIONS_FOR_MASTERY = 3


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensures a datetime is timezone-aware in UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class MasteryResult:
    score: float
    tier: str  # "mastered" | "proficient" | "needs_practice" | "unassessed"
    is_assessed: bool
    attempted_count: int
    questions_needed: int
    last_attempted_at: Optional[datetime]


@dataclass
class TopicMasteryItem:
    document_id: Optional[str]
    document_title: str
    topic_key: str
    topic_display: str
    mastery: MasteryResult
    is_archived: bool


@dataclass
class DocumentMasteryItem:
    document_id: Optional[str]
    document_title: str
    mastery: MasteryResult
    is_archived: bool


@dataclass
class OverallMasterySummary:
    overall_attempt_accuracy: float
    total_completed_sessions: int
    total_attempted_questions: int
    total_attempts: int
    document_masteries: list[DocumentMasteryItem]
    topic_masteries: list[TopicMasteryItem]


def calculate_mastery_for_attempts(
    attempt_tuples: list[tuple[float, datetime]],
    now: Optional[datetime] = None,
) -> MasteryResult:
    """
    Calculates recency-decayed mastery for a collection of (score, attempt_timestamp) pairs,
    where each pair represents the latest attempt on a distinct question.

    - Formula: Weighted average with weights w_i = e^(-lambda * delta_t_days)
    - Eligibility threshold: At least 3 distinct attempted questions are required
      before assigning an assessed tier.
    """
    ref_time = ensure_utc(now) or datetime.now(timezone.utc)
    attempted_count = len(attempt_tuples)

    if attempted_count == 0:
        return MasteryResult(
            score=0.0,
            tier="unassessed",
            is_assessed=False,
            attempted_count=0,
            questions_needed=MIN_QUESTIONS_FOR_MASTERY,
            last_attempted_at=None,
        )

    sum_weighted_scores = 0.0
    sum_weights = 0.0
    latest_ts: Optional[datetime] = None

    for score, ts in attempt_tuples:
        utc_ts = ensure_utc(ts) or ref_time
        if latest_ts is None or utc_ts > latest_ts:
            latest_ts = utc_ts

        delta_seconds = max(0.0, (ref_time - utc_ts).total_seconds())
        delta_days = delta_seconds / 86400.0
        weight = math.exp(-LAMBDA_DECAY * delta_days)

        sum_weighted_scores += float(score) * weight
        sum_weights += weight

    if sum_weights > 0.0:
        raw_score = sum_weighted_scores / sum_weights
        final_score = round(max(0.0, min(1.0, raw_score)), 4)
    else:
        final_score = 0.0

    is_assessed = attempted_count >= MIN_QUESTIONS_FOR_MASTERY
    questions_needed = max(0, MIN_QUESTIONS_FOR_MASTERY - attempted_count)

    if not is_assessed:
        tier = "unassessed"
    elif final_score >= 0.85:
        tier = "mastered"
    elif final_score >= 0.60:
        tier = "proficient"
    else:
        tier = "needs_practice"

    return MasteryResult(
        score=final_score,
        tier=tier,
        is_assessed=is_assessed,
        attempted_count=attempted_count,
        questions_needed=questions_needed,
        last_attempted_at=latest_ts,
    )


def calculate_mastery_for_questions(
    questions: list[RevisionQuestion],
    now: Optional[datetime] = None,
) -> MasteryResult:
    """
    Calculates mastery over a list of RevisionQuestions.
    Only questions with at least one attempt are considered.
    Uses the latest attempt per question.
    """
    attempt_tuples: list[tuple[float, datetime]] = []

    for q in questions:
        attempts = q.attempts
        if not attempts:
            continue
        latest = max(attempts, key=lambda a: a.attempt_number)
        attempt_tuples.append((float(latest.score), latest.created_at))

    return calculate_mastery_for_attempts(attempt_tuples, now=now)


def get_completed_sessions_for_identity(
    db: Session,
    identity: Identity,
) -> list[RevisionSession]:
    """
    Retrieves all completed RevisionSessions owned by the specified identity,
    eagerly loading questions and attempts.
    """
    return (
        db.query(RevisionSession)
        .options(
            joinedload(RevisionSession.questions).joinedload(RevisionQuestion.attempts)
        )
        .filter(
            RevisionSession.owner_type == identity.type.value,
            RevisionSession.owner_id == identity.id,
            RevisionSession.status == "completed",
        )
        .order_by(RevisionSession.completed_at.desc(), RevisionSession.created_at.desc())
        .all()
    )


def _resolve_document_info(
    question: RevisionQuestion,
    active_docs_by_id: dict[str, Document],
) -> tuple[Optional[str], str, bool]:
    """
    Resolves (document_id, document_title, is_archived) for a question.
    Handles active documents, deleted documents, and legacy metadata snapshots.
    """
    meta = question.evidence_metadata or {}
    doc_id = question.source_document_id or meta.get("source_document_id")

    if doc_id and doc_id in active_docs_by_id:
        active_doc = active_docs_by_id[doc_id]
        return active_doc.id, active_doc.original_filename, False

    # Document is deleted or was created without foreign key
    title = meta.get("document_title") or "Archived Document"
    return doc_id, title, True


def get_overall_mastery(
    db: Session,
    identity: Identity,
    now: Optional[datetime] = None,
) -> OverallMasterySummary:
    """
    Computes overall, document-level, and topic-level mastery metrics on-demand
    for the calling identity across all completed RevisionSessions.
    """
    sessions = get_completed_sessions_for_identity(db, identity)

    # Pre-fetch all active documents owned by this identity to resolve titles/status
    active_docs = (
        db.query(Document)
        .filter(
            Document.owner_type == identity.type.value,
            Document.owner_id == identity.id,
        )
        .all()
    )
    active_docs_by_id = {d.id: d for d in active_docs}

    total_completed_sessions = len(sessions)
    total_attempts = 0

    all_attempted_scores: list[float] = []

    # Map: doc_key -> list of (score, timestamp)
    doc_attempts_map: dict[str, list[tuple[float, datetime]]] = {}
    doc_info_map: dict[str, tuple[Optional[str], str, bool]] = {}

    # Map: (doc_key, topic_key) -> list of (score, timestamp)
    topic_attempts_map: dict[tuple[str, str], list[tuple[float, datetime]]] = {}
    # Track the latest display label and question timestamp for each topic group
    topic_display_map: dict[tuple[str, str], tuple[str, datetime]] = {}

    for s in sessions:
        for q in s.questions:
            attempts = q.attempts
            total_attempts += len(attempts)

            if not attempts:
                # Unanswered question: excluded from mastery evidence
                continue

            latest_attempt = max(attempts, key=lambda a: a.attempt_number)
            score = float(latest_attempt.score)
            ts = latest_attempt.created_at
            all_attempted_scores.append(score)

            doc_id, doc_title, is_archived = _resolve_document_info(q, active_docs_by_id)
            doc_key = f"id:{doc_id}" if doc_id else f"title:{doc_title}"

            if doc_key not in doc_attempts_map:
                doc_attempts_map[doc_key] = []
                doc_info_map[doc_key] = (doc_id, doc_title, is_archived)

            doc_attempts_map[doc_key].append((score, ts))

            # Topic attribution
            meta = q.evidence_metadata or {}
            topic_key = meta.get("topic_key")
            topic_display = meta.get("topic")

            if not topic_key and topic_display:
                norm = clean_and_normalize_topic(topic_display)
                if norm:
                    topic_display, topic_key = norm

            if topic_key:
                group_key = (doc_key, topic_key)
                if group_key not in topic_attempts_map:
                    topic_attempts_map[group_key] = []
                    topic_display_map[group_key] = (
                        topic_display or topic_key.title(),
                        ensure_utc(ts) or datetime.min.replace(tzinfo=timezone.utc),
                    )
                else:
                    # Update display label if this attempt is more recent
                    cur_disp, cur_ts = topic_display_map[group_key]
                    utc_ts = ensure_utc(ts) or datetime.min.replace(tzinfo=timezone.utc)
                    if utc_ts >= cur_ts and topic_display:
                        topic_display_map[group_key] = (topic_display, utc_ts)

                topic_attempts_map[group_key].append((score, ts))

    # Overall accuracy
    if all_attempted_scores:
        overall_accuracy = round(sum(all_attempted_scores) / len(all_attempted_scores), 4)
    else:
        overall_accuracy = 0.0

    # Build document mastery list
    document_masteries: list[DocumentMasteryItem] = []
    for doc_key, attempts_list in doc_attempts_map.items():
        doc_id, doc_title, is_archived = doc_info_map[doc_key]
        mastery = calculate_mastery_for_attempts(attempts_list, now=now)
        document_masteries.append(
            DocumentMasteryItem(
                document_id=doc_id,
                document_title=doc_title,
                mastery=mastery,
                is_archived=is_archived,
            )
        )

    # Sort documents: active first by title, then archived
    document_masteries.sort(key=lambda d: (d.is_archived, d.document_title.casefold()))

    # Build topic mastery list
    topic_masteries: list[TopicMasteryItem] = []
    for (doc_key, topic_key), attempts_list in topic_attempts_map.items():
        doc_id, doc_title, is_archived = doc_info_map[doc_key]
        topic_disp, _ = topic_display_map[(doc_key, topic_key)]
        mastery = calculate_mastery_for_attempts(attempts_list, now=now)
        topic_masteries.append(
            TopicMasteryItem(
                document_id=doc_id,
                document_title=doc_title,
                topic_key=topic_key,
                topic_display=topic_disp,
                mastery=mastery,
                is_archived=is_archived,
            )
        )

    # Sort topics: by document title, then topic display
    topic_masteries.sort(key=lambda t: (t.document_title.casefold(), t.topic_display.casefold()))

    return OverallMasterySummary(
        overall_attempt_accuracy=overall_accuracy,
        total_completed_sessions=total_completed_sessions,
        total_attempted_questions=len(all_attempted_scores),
        total_attempts=total_attempts,
        document_masteries=document_masteries,
        topic_masteries=topic_masteries,
    )


def get_document_mastery(
    db: Session,
    identity: Identity,
    document_id: str,
    now: Optional[datetime] = None,
) -> Optional[DocumentMasteryItem]:
    """
    Returns mastery metrics for a single specific document.
    """
    summary = get_overall_mastery(db, identity, now=now)
    for dm in summary.document_masteries:
        if dm.document_id == document_id:
            return dm
    return None

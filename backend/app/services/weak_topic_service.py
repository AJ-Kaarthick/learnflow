import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Document, RevisionQuestion
from app.schemas.identity import Identity
from app.services.mastery_service import (
    calculate_mastery_for_attempts,
    ensure_utc,
    get_completed_sessions_for_identity,
    resolve_document_info,
)
from app.services.revision_service import clean_and_normalize_topic

MIN_QUESTIONS_FOR_WEAK_TOPIC = 3
WEAK_TOPIC_MASTERY_THRESHOLD = 0.60
WEAK_TOPIC_INCORRECT_RATIO_THRESHOLD = 0.50


@dataclass
class WeakTopicItem:
    """
    Represents a detected weak topic for an identity with struggle metrics and provenance.
    """
    document_id: Optional[str]
    document_title: str
    is_archived: bool
    is_actionable: bool
    topic_key: str
    topic_display: str
    mastery_score: float
    mastery_tier: str
    distinct_attempted_questions: int
    incorrect_questions_count: int
    incorrect_ratio: float
    total_attempts: int
    struggle_index: float
    last_attempted_at: Optional[datetime]


def calculate_struggle_index(mastery_score: float, total_attempts: int) -> float:
    """
    Calculates struggle index according to M5 specification:
    StruggleIndex = (1 - MasteryScore) * ln(1 + TotalAttempts)
    """
    raw = (1.0 - float(mastery_score)) * math.log(1.0 + max(0, total_attempts))
    return round(max(0.0, raw), 4)


def detect_weak_topics(
    db: Session,
    identity: Identity,
    now: Optional[datetime] = None,
) -> list[WeakTopicItem]:
    """
    Detects weak topics on demand for the requested identity from completed RevisionSessions.

    Eligibility:
    - At least 3 distinct attempted questions required.

    Weakness criteria (either condition met):
    1. Phase 1 recency-decayed mastery score strictly below 0.60.
    2. More than 50% of distinct attempted questions have a latest attempt with is_correct=False.

    Ordering:
    Deterministic order by struggle_index DESC, mastery_score ASC, document_title ASC, topic_display ASC.
    """
    sessions = get_completed_sessions_for_identity(db, identity)

    # Pre-fetch all active documents owned by this identity
    active_docs = (
        db.query(Document)
        .filter(
            Document.owner_type == identity.type.value,
            Document.owner_id == identity.id,
        )
        .all()
    )
    active_docs_by_id = {d.id: d for d in active_docs}

    # Group questions by (doc_key, topic_key)
    # Map: (doc_key, topic_key) -> list of RevisionQuestion
    topic_questions_map: dict[tuple[str, str], list[RevisionQuestion]] = {}
    doc_info_map: dict[str, tuple[Optional[str], str, bool]] = {}
    topic_display_map: dict[tuple[str, str], tuple[str, datetime]] = {}

    for s in sessions:
        for q in s.questions:
            # Questions with no attempts do not count toward weak-topic evidence threshold
            if not q.attempts:
                continue

            doc_id, doc_title, is_archived = resolve_document_info(q, active_docs_by_id)
            doc_key = f"id:{doc_id}" if doc_id else f"title:{doc_title}"

            if doc_key not in doc_info_map:
                doc_info_map[doc_key] = (doc_id, doc_title, is_archived)

            meta = q.evidence_metadata or {}
            topic_key = meta.get("topic_key")
            topic_display = meta.get("topic")

            if not topic_key and topic_display:
                norm = clean_and_normalize_topic(topic_display)
                if norm:
                    topic_display, topic_key = norm

            # Legacy questions with no valid topic attribution remain eligible for document-level/overall
            # statistics, but must not be given fabricated topic labels
            if not topic_key:
                continue

            group_key = (doc_key, topic_key)
            if group_key not in topic_questions_map:
                topic_questions_map[group_key] = []
                latest_q_ts = max(
                    (ensure_utc(a.created_at) or datetime.min.replace(tzinfo=timezone.utc))
                    for a in q.attempts
                )
                topic_display_map[group_key] = (
                    topic_display or topic_key.title(),
                    latest_q_ts,
                )
            else:
                # Update readable display label if this question has more recent attempt
                cur_disp, cur_ts = topic_display_map[group_key]
                latest_q_ts = max(
                    (ensure_utc(a.created_at) or datetime.min.replace(tzinfo=timezone.utc))
                    for a in q.attempts
                )
                if latest_q_ts >= cur_ts and topic_display:
                    topic_display_map[group_key] = (topic_display, latest_q_ts)

            topic_questions_map[group_key].append(q)

    weak_topics: list[WeakTopicItem] = []

    for (doc_key, topic_key), questions in topic_questions_map.items():
        doc_id, doc_title, is_archived = doc_info_map[doc_key]
        topic_disp, _ = topic_display_map[(doc_key, topic_key)]

        # Each RevisionQuestion is a distinct question row
        distinct_count = len(questions)
        if distinct_count < MIN_QUESTIONS_FOR_WEAK_TOPIC:
            continue

        total_attempts = 0
        incorrect_distinct_count = 0
        attempt_tuples: list[tuple[float, datetime]] = []

        for q in questions:
            attempts = q.attempts
            total_attempts += len(attempts)

            latest_attempt = max(attempts, key=lambda a: a.attempt_number)
            attempt_tuples.append((float(latest_attempt.score), latest_attempt.created_at))

            if not latest_attempt.is_correct:
                incorrect_distinct_count += 1

        incorrect_ratio = round(incorrect_distinct_count / distinct_count, 4)

        mastery_res = calculate_mastery_for_attempts(attempt_tuples, now=now)
        mastery_score = mastery_res.score

        # Weakness condition:
        # 1. Mastery score strictly below 0.60
        # 2. More than 50% incorrect distinct attempted questions
        is_weak = (mastery_score < WEAK_TOPIC_MASTERY_THRESHOLD) or (
            incorrect_distinct_count / distinct_count > WEAK_TOPIC_INCORRECT_RATIO_THRESHOLD
        )

        if not is_weak:
            continue

        struggle_idx = calculate_struggle_index(mastery_score, total_attempts)

        weak_topics.append(
            WeakTopicItem(
                document_id=doc_id,
                document_title=doc_title,
                is_archived=is_archived,
                is_actionable=not is_archived,
                topic_key=topic_key,
                topic_display=topic_disp,
                mastery_score=mastery_score,
                mastery_tier=mastery_res.tier,
                distinct_attempted_questions=distinct_count,
                incorrect_questions_count=incorrect_distinct_count,
                incorrect_ratio=incorrect_ratio,
                total_attempts=total_attempts,
                struggle_index=struggle_idx,
                last_attempted_at=mastery_res.last_attempted_at,
            )
        )

    # Deterministic sorting:
    # 1. Highest struggle index first
    # 2. Lower mastery score first
    # 3. Document title alphabetical
    # 4. Topic display alphabetical
    # 5. Document ID
    weak_topics.sort(
        key=lambda item: (
            -item.struggle_index,
            item.mastery_score,
            item.document_title.casefold(),
            item.topic_display.casefold(),
            item.document_id or "",
        )
    )

    return weak_topics


def detect_weak_topics_for_document(
    db: Session,
    identity: Identity,
    document_id: str,
    now: Optional[datetime] = None,
) -> list[WeakTopicItem]:
    """
    Convenience method returning weak topics restricted to a specific document ID.
    """
    all_weak = detect_weak_topics(db, identity, now=now)
    return [wt for wt in all_weak if wt.document_id == document_id]

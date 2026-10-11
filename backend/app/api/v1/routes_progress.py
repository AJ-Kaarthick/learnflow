from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_identity
from app.db.database import get_db
from app.schemas.identity import Identity
from app.schemas.progress import (
    ProgressSummaryResponse,
    RecommendationResponseItem,
    SpacedRepetitionScheduleResponseItem,
    TopicMasteryResponseItem,
    WeakTopicResponseItem,
)
from app.services.progress_service import get_progress_summary, get_progress_topics
from app.services.recommendation_service import get_recommendations
from app.services.spaced_repetition_service import get_review_schedules
from app.services.weak_topic_service import detect_weak_topics

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/summary", response_model=ProgressSummaryResponse)
def get_progress_summary_endpoint(
    identity: Identity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> ProgressSummaryResponse:
    """
    Computes overall progress metrics, activity timelines, difficulty distributions,
    and flashcard metrics on demand for the calling identity.
    """
    return get_progress_summary(db=db, identity=identity)


@router.get("/topics", response_model=list[TopicMasteryResponseItem])
def get_progress_topics_endpoint(
    identity: Identity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> list[TopicMasteryResponseItem]:
    """
    Returns topic-level mastery items using Phase 1 mastery service,
    preserving composite grouping by (source_document_identity, normalized_topic_key).
    """
    return get_progress_topics(db=db, identity=identity)


@router.get("/weak-topics", response_model=list[WeakTopicResponseItem])
def get_weak_topics_endpoint(
    identity: Identity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> list[WeakTopicResponseItem]:
    """
    Returns detected weak topics for the calling identity using Phase 2 weak-topic service,
    ranked deterministically by struggle index and mastery score.
    """
    weak_topics = detect_weak_topics(db=db, identity=identity)
    return [
        WeakTopicResponseItem(
            document_id=wt.document_id,
            document_title=wt.document_title,
            is_archived=wt.is_archived,
            is_actionable=wt.is_actionable,
            topic_key=wt.topic_key,
            topic_display=wt.topic_display,
            mastery_score=wt.mastery_score,
            mastery_tier=wt.mastery_tier,
            distinct_attempted_questions=wt.distinct_attempted_questions,
            incorrect_questions_count=wt.incorrect_questions_count,
            incorrect_ratio=wt.incorrect_ratio,
            total_attempts=wt.total_attempts,
            struggle_index=wt.struggle_index,
            last_attempted_at=wt.last_attempted_at,
        )
        for wt in weak_topics
    ]


@router.get("/spaced-repetition", response_model=list[SpacedRepetitionScheduleResponseItem])
def get_spaced_repetition_endpoint(
    include_unreviewed_active: bool = Query(
        default=True,
        description="Whether to include active unreviewed documents with baseline unreviewed state",
    ),
    identity: Identity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> list[SpacedRepetitionScheduleResponseItem]:
    """
    Derives spaced-repetition review schedules from completed RevisionSession history
    for the calling identity using Phase 2 spaced-repetition service.
    """
    schedules = get_review_schedules(
        db=db,
        identity=identity,
        include_unreviewed_active=include_unreviewed_active,
    )
    return [
        SpacedRepetitionScheduleResponseItem(
            document_id=s.document_id,
            document_title=s.document_title,
            is_archived=s.is_archived,
            is_actionable=s.is_actionable,
            has_history=s.has_history,
            latest_review_score=s.latest_review_score,
            last_reviewed_at=s.last_reviewed_at,
            current_streak=s.current_streak,
            interval_days=s.interval_days,
            next_review_due=s.next_review_due,
            is_due=s.is_due,
        )
        for s in schedules
    ]


@router.get("/recommendations", response_model=list[RecommendationResponseItem])
def get_recommendations_endpoint(
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        description="Optional maximum number of recommendations to return",
    ),
    identity: Identity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> list[RecommendationResponseItem]:
    """
    Returns deterministic, on-demand adaptive learning recommendations
    strictly adhering to the M5 priority hierarchy (due review -> weak topic practice -> unrevised document).
    """
    return get_recommendations(db=db, identity=identity, limit=limit)

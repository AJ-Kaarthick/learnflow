from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MasteryResultSchema(BaseModel):
    """
    Recency-decayed mastery result.
    """
    score: float
    tier: str  # "mastered" | "proficient" | "needs_practice" | "unassessed"
    is_assessed: bool
    attempted_count: int
    questions_needed: int
    last_attempted_at: Optional[datetime] = None


class DailyActivityItem(BaseModel):
    """
    Daily revision activity bucket.
    """
    date: str  # YYYY-MM-DD
    total_attempts: int
    questions_attempted: int
    sessions_completed: int
    average_score: Optional[float] = None


class ActivityWindowSummary(BaseModel):
    """
    Summary metrics over an N-day activity window.
    """
    days: int
    total_attempts: int
    questions_attempted: int
    sessions_completed: int
    average_score: Optional[float] = None
    timeline: list[DailyActivityItem]


class ActivityWindowsSchema(BaseModel):
    """
    Continuous daily activity windows for 7, 14, and 30 days.
    """
    last_7_days: ActivityWindowSummary
    last_14_days: ActivityWindowSummary
    last_30_days: ActivityWindowSummary


class DifficultyDistributionItem(BaseModel):
    """
    Performance and mastery breakdown by difficulty level.
    """
    difficulty: str  # "beginner" | "intermediate" | "advanced"
    distinct_attempted_questions: int
    total_attempts: int
    average_score: Optional[float] = None
    mastery: MasteryResultSchema


class FlashcardMetricsSchema(BaseModel):
    """
    Dedicated recall metrics for Revision flashcard sessions.
    """
    distinct_questions_reviewed: int
    total_attempts: int
    recall_rate: Optional[float] = None
    mastery: MasteryResultSchema


class ProgressSummaryResponse(BaseModel):
    """
    Full learning intelligence progress summary response.
    """
    overall_mastery: MasteryResultSchema
    total_completed_sessions: int
    total_questions_generated: int
    total_attempted_questions: int
    total_unanswered_questions: int
    total_attempts: int
    overall_attempt_accuracy: float
    mean_session_score: float
    activity_timeline: list[DailyActivityItem]
    activity_windows: ActivityWindowsSchema
    difficulty_distribution: list[DifficultyDistributionItem]
    flashcard_metrics: FlashcardMetricsSchema


class TopicMasteryResponseItem(BaseModel):
    """
    Topic-level mastery response item with document provenance.
    """
    document_id: Optional[str] = None
    document_title: str
    is_archived: bool
    topic_key: str
    topic_display: str
    mastery_score: float
    mastery_tier: str
    is_assessed: bool
    distinct_attempted_questions: int
    questions_needed: int
    last_attempted_at: Optional[datetime] = None


class WeakTopicResponseItem(BaseModel):
    """
    Detected weak topic with struggle index and assessment metrics.
    """
    document_id: Optional[str] = None
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
    last_attempted_at: Optional[datetime] = None


class SpacedRepetitionScheduleResponseItem(BaseModel):
    """
    Spaced repetition document review schedule item.
    """
    document_id: Optional[str] = None
    document_title: str
    is_archived: bool
    is_actionable: bool
    has_history: bool
    latest_review_score: Optional[float] = None
    last_reviewed_at: Optional[datetime] = None
    current_streak: int
    interval_days: Optional[int] = None
    next_review_due: Optional[datetime] = None
    is_due: bool


class RecommendationActionPayload(BaseModel):
    """
    Structured launcher parameters for starting a Revision session from a recommendation.
    """
    document_ids: list[str]
    mode: str = "practice"
    difficulty: str = "intermediate"
    question_count: int = 5
    question_type: str = "multiple_choice"
    topic_focus: Optional[str] = None


class RecommendationResponseItem(BaseModel):
    """
    Actionable revision recommendation grounded in learning progress.
    """
    id: str
    type: Literal["spaced_review", "weak_topic_practice", "unrevised_document"]
    priority: int  # 1 (spaced_review), 2 (weak_topic_practice), 3 (unrevised_document)
    title: str
    reason: str
    document_id: str
    document_title: str
    is_archived: bool
    is_actionable: bool
    topic_focus: Optional[str] = None
    urgency: Optional[float] = None
    due_date: Optional[datetime] = None
    struggle_index: Optional[float] = None
    mastery_score: Optional[float] = None
    action_payload: RecommendationActionPayload

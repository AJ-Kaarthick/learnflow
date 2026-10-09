import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.chat import MAX_DOCUMENT_IDS

# Cap on document count for revision sessions, matching chat/learn conventions.
MAX_REVISION_DOCUMENT_IDS = MAX_DOCUMENT_IDS
MAX_REVISION_TITLE_LENGTH = 200
DEFAULT_QUESTION_COUNT = 5
MIN_QUESTION_COUNT = 1
MAX_QUESTION_COUNT = 20

RevisionDifficulty = Literal["beginner", "intermediate", "advanced"]
RevisionMode = Literal["practice", "quiz", "flashcards"]
RevisionQuestionType = Literal["multiple_choice", "open_ended"]
RevisionQuestionTypeFilter = Literal["multiple_choice", "open_ended", "mixed"]


def normalize_topic_focus(value: Optional[str]) -> Optional[str]:
    """
    Validates and normalizes an untrusted topic_focus string:
    - Rejects control characters (Unicode category C) and newlines.
    - Applies Unicode NFKC normalization.
    - Strips surrounding quotes, backticks, brackets, and whitespace.
    - Collapses internal whitespace runs.
    - Enforces length between 2 and 100 characters after normalization.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("topic_focus must be a string.")
    if any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("topic_focus must not contain control characters or newlines.")
    if "\r" in value or "\n" in value or "\x00" in value:
        raise ValueError("topic_focus must not contain control characters or newlines.")
    normalized = unicodedata.normalize("NFKC", value)
    cleaned = re.sub(r"\s+", " ", normalized).strip()
    cleaned = cleaned.strip("\"'`[]{}()")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) < 2 or len(cleaned) > 100:
        raise ValueError("topic_focus must be between 2 and 100 characters after normalization.")
    return cleaned


def _assume_utc(value: object) -> object:
    """
    Restores timezone.utc to naive datetimes returned by SQLite.
    """
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class RevisionSessionCreateRequest(BaseModel):
    """
    Request body for POST /api/v1/revision/sessions.
    Configures a new revision session spanning 1 to 10 documents.
    """

    document_ids: list[str] = Field(min_length=1, max_length=MAX_REVISION_DOCUMENT_IDS)
    title: Optional[str] = Field(default=None, max_length=MAX_REVISION_TITLE_LENGTH)
    difficulty: RevisionDifficulty = "intermediate"
    mode: RevisionMode = "practice"
    question_type: RevisionQuestionTypeFilter = "multiple_choice"
    question_count: int = Field(
        default=DEFAULT_QUESTION_COUNT,
        ge=MIN_QUESTION_COUNT,
        le=MAX_QUESTION_COUNT,
    )
    topic_focus: Optional[str] = Field(default=None)

    @field_validator("document_ids")
    @classmethod
    def deduplicate_preserving_order(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduplicated: list[str] = []
        for doc_id in value:
            clean_id = (doc_id or "").strip()
            if clean_id and clean_id not in seen:
                seen.add(clean_id)
                deduplicated.append(clean_id)
        if not deduplicated:
            raise ValueError("document_ids must contain at least one valid non-empty document ID.")
        return deduplicated

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("topic_focus")
    @classmethod
    def clean_topic_focus(cls, value: Optional[str]) -> Optional[str]:
        return normalize_topic_focus(value)


class RevisionAttemptSubmitRequest(BaseModel):
    """
    Request body for submitting an answer attempt to a RevisionQuestion.
    """

    submitted_answer: str = Field(default="", max_length=10000)


class RevisionAttemptResponse(BaseModel):
    """
    Evaluated response for a single attempt on a RevisionQuestion.
    """

    id: str
    question_id: str
    session_id: str
    attempt_number: int
    submitted_answer: str
    is_correct: bool
    score: float
    feedback: Optional[str] = None
    explanation: Optional[str] = None
    correct_answer: Optional[str] = None
    evaluation_metadata: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _created_at_is_utc(cls, value: object) -> object:
        return _assume_utc(value)


class RevisionQuestionResponse(BaseModel):
    """
    Schema representing one persistent revision question.
    Preserves durable evidence citations even if the source document is later deleted.
    """

    id: str
    session_id: str
    position: int
    question_type: str
    question_text: str
    options: Optional[list[str]] = None
    correct_answer: str
    explanation: Optional[str] = None
    source_document_id: Optional[str] = None
    source_document_title: Optional[str] = None
    source_chunk_id: Optional[str] = None
    evidence_snippet: Optional[str] = None
    evidence_metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    attempts: list[RevisionAttemptResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _created_at_is_utc(cls, value: object) -> object:
        return _assume_utc(value)


class RevisionSessionDocumentSummary(BaseModel):
    """
    Trimmed summary of a document bound to a RevisionSession.
    """

    document_id: str
    original_filename: str
    status: str
    added_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("added_at", mode="before")
    @classmethod
    def _added_at_is_utc(cls, value: object) -> object:
        return _assume_utc(value)


class RevisionSessionSummaryResponse(BaseModel):
    """
    Summary shape returned in session listings (GET /api/v1/revision/sessions).
    """

    id: str
    title: str
    owner_type: str
    owner_id: str
    status: str
    config: Optional[dict[str, Any]] = None
    total_questions: int
    score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    document_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_validator("created_at", "completed_at", mode="before")
    @classmethod
    def _timestamps_are_utc(cls, value: object) -> object:
        return _assume_utc(value)


class RevisionSessionDetailResponse(RevisionSessionSummaryResponse):
    """
    Full session details returned on creation (POST /sessions)
    and retrieval (GET /sessions/{id}), including bound documents and generated questions.
    """

    documents: list[RevisionSessionDocumentSummary] = Field(default_factory=list)
    questions: list[RevisionQuestionResponse] = Field(default_factory=list)

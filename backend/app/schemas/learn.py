from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.chat import MAX_DOCUMENT_IDS

LearnDepth = Literal["overview", "standard", "in-depth"]
LearnAction = Literal["simplify", "elaborate", "example"]
MAX_LEARN_DOCUMENT_IDS = MAX_DOCUMENT_IDS


class LearnOutlineRequest(BaseModel):
    """
    Request body for POST /api/v1/study/learn/outline.
    Accepts 1 to 10 document IDs and an optional depth control.
    """

    document_ids: list[str] = Field(min_length=1, max_length=MAX_DOCUMENT_IDS)
    depth: LearnDepth = "standard"

    @field_validator("document_ids")
    @classmethod
    def deduplicate_preserving_order(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduplicated = []
        for document_id in value:
            if document_id not in seen:
                seen.add(document_id)
                deduplicated.append(document_id)
        if not deduplicated:
            raise ValueError("document_ids cannot be empty.")
        return deduplicated


class LearnSubtopic(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None


class LearnTopic(BaseModel):
    id: str
    title: str
    description: str
    learning_objectives: list[str] = Field(default_factory=list)
    subtopics: list[LearnSubtopic] = Field(default_factory=list)


class LearnContributingDocument(BaseModel):
    id: str
    original_filename: str
    character_count: int


class LearnExcludedDocument(BaseModel):
    id: str
    original_filename: str
    reason: str


class LearnOutlineProvenance(BaseModel):
    document_ids: list[str]
    contributing_documents: list[LearnContributingDocument] = Field(default_factory=list)
    excluded_documents: list[LearnExcludedDocument] = Field(default_factory=list)
    total_topics: int
    depth: str


class LearnOutlineResponse(BaseModel):
    document_ids: list[str]
    title: str
    description: str
    topics: list[LearnTopic]
    learning_objectives: list[str] = Field(default_factory=list)
    grounding_metadata: LearnOutlineProvenance


class LearnTopicRequest(BaseModel):
    """
    Request body for POST /api/v1/study/learn/topic.
    Accepts 1 to 10 document IDs, topic identifier, topic title,
    optional contextual action, and depth.
    """

    document_ids: list[str] = Field(min_length=1, max_length=MAX_DOCUMENT_IDS)
    topic_id: str = Field(min_length=1)
    topic_title: str = Field(min_length=1)
    action: Optional[LearnAction] = None
    depth: LearnDepth = "standard"
    parent_topic_title: Optional[str] = None
    context: Optional[str] = None

    @field_validator("document_ids")
    @classmethod
    def deduplicate_preserving_order(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduplicated = []
        for document_id in value:
            if document_id not in seen:
                seen.add(document_id)
                deduplicated.append(document_id)
        if not deduplicated:
            raise ValueError("document_ids cannot be empty.")
        return deduplicated

    @field_validator("topic_id", "topic_title")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field cannot be blank.")
        return stripped


class LearnKeyTerm(BaseModel):
    term: str
    definition: str


class LearnSourceCitation(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    chunk_index: int
    content: str
    score: float


class LearnTopicGroundingMetadata(BaseModel):
    grounded: bool
    retrieved_chunks_count: int
    document_ids: list[str]
    depth: str
    action: Optional[str] = None


class LearnTopicResponse(BaseModel):
    topic_id: str
    topic_title: str
    action: Optional[str] = None
    depth: str = "standard"
    explanation: str
    key_terms: list[LearnKeyTerm] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    sources: list[LearnSourceCitation] = Field(default_factory=list)
    grounding_metadata: LearnTopicGroundingMetadata

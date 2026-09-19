from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.chat import MAX_DOCUMENT_IDS
from app.schemas.learn import LearnContributingDocument, LearnExcludedDocument

VisualizeDepth = Literal["overview", "standard", "in-depth"]
MAX_VISUALIZE_DOCUMENT_IDS = MAX_DOCUMENT_IDS

# Bounded graph sizes per depth to avoid unbounded AI output and maintain visual readability
MAX_NODES_PER_DEPTH: dict[str, int] = {
    "overview": 10,
    "standard": 16,
    "in-depth": 22,
}

MAX_EDGES_PER_DEPTH: dict[str, int] = {
    "overview": 15,
    "standard": 26,
    "in-depth": 36,
}


class VisualizeGraphRequest(BaseModel):
    """
    Request body for POST /api/v1/study/visualize/graph.
    Accepts 1 to 10 document IDs and an optional depth control.
    """

    document_ids: list[str] = Field(min_length=1, max_length=MAX_VISUALIZE_DOCUMENT_IDS)
    depth: VisualizeDepth = "standard"

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


class VisualizeConceptNode(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    category: str = Field(min_length=1)
    document_ids: list[str] = Field(default_factory=list)
    importance: float = Field(default=1.0, ge=0.5, le=3.0)


class VisualizeConceptEdge(BaseModel):
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    label: str = Field(default="relates to")


class VisualizeSourceCitation(BaseModel):
    node_id: str
    document_id: str
    document_name: str
    chunk_id: str
    chunk_index: int
    content: str
    score: float


class VisualizeProvenance(BaseModel):
    document_ids: list[str]
    contributing_documents: list[LearnContributingDocument] = Field(default_factory=list)
    excluded_documents: list[LearnExcludedDocument] = Field(default_factory=list)
    total_nodes: int
    total_edges: int
    depth: str


class VisualizeGraphResponse(BaseModel):
    document_ids: list[str]
    title: str
    summary: str
    nodes: list[VisualizeConceptNode]
    edges: list[VisualizeConceptEdge]
    citations: list[VisualizeSourceCitation] = Field(default_factory=list)
    grounding_metadata: VisualizeProvenance

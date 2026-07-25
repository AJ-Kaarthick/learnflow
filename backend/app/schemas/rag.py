from pydantic import BaseModel, field_validator

# Mirrors DEFAULT_QUESTION_COUNT in quiz_service.py — a sane default
# for "how many results" that the caller can still override per
# request via SearchRequest.top_k below.
DEFAULT_TOP_K = 5


class IndexResponse(BaseModel):
    """
    What POST /documents/{id}/index returns. Deliberately doesn't
    include the chunks themselves (that's what search is for) — this
    endpoint answers "did indexing work, and how much did it produce,"
    not "show me the content."
    """

    document_id: str
    chunk_count: int

    # "already_indexed" (idempotent no-op, same as calling
    # POST /summary twice) vs "indexed" (this call did the work) —
    # lets a caller tell the two apart without a second request.
    status: str


class SearchRequest(BaseModel):
    """Body for POST /documents/{id}/search."""

    query: str
    top_k: int = DEFAULT_TOP_K

    @field_validator("query")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query cannot be empty.")
        return stripped

    @field_validator("top_k")
    @classmethod
    def positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("top_k must be at least 1.")
        return value


class SearchResultItem(BaseModel):
    """One scored chunk in a search response, most similar chunks first."""

    chunk_id: str
    chunk_index: int
    content: str

    # Cosine similarity to the query, from -1.0 to 1.0 (in practice,
    # text embeddings rarely produce negative scores — see
    # _cosine_similarity's docstring in retrieval_service.py). Exposed
    # rather than hidden so a future feature (or a developer testing
    # this endpoint by hand) can judge how *confident* a match is, not
    # just its rank — a top result with a score of 0.3 means something
    # very different from one with a score of 0.9.
    score: float


class SearchResponse(BaseModel):
    document_id: str
    query: str
    results: list[SearchResultItem]

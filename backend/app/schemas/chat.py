from pydantic import BaseModel, field_validator

from app.schemas.rag import SearchResultItem

# Mirrors DEFAULT_TOP_K in schemas/rag.py — same default, same reason.
DEFAULT_TOP_K = 5


class ChatRequest(BaseModel):
    """
    Body for POST /documents/{id}/chat. Deliberately just one question
    today — no conversation_id, no message history. This is a
    single-turn endpoint by design, not a stripped-down multi-turn one:
    adding conversation history later means adding new optional fields
    to this same model (e.g. an optional conversation_id), which is an
    additive change existing callers wouldn't need to react to, not a
    breaking one.
    """

    question: str
    top_k: int = DEFAULT_TOP_K

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question cannot be empty.")
        return stripped

    @field_validator("top_k")
    @classmethod
    def positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("top_k must be at least 1.")
        return value


class ChatResponse(BaseModel):
    document_id: str
    question: str
    answer: str

    # False only when there was no indexed context at all to answer
    # from (see chat_service.answer_question) — lets a caller tell
    # "the document says X isn't covered" apart from "there was
    # nothing to even check" without parsing the answer text itself.
    grounded: bool

    # Reuses SearchResultItem (schemas/rag.py) rather than a new,
    # identical class — a chat source and a search result are the same
    # thing: a chunk plus how well it matched a query.
    sources: list[SearchResultItem]

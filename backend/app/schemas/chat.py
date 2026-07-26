from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.rag import SearchResultItem

# Mirrors DEFAULT_TOP_K in schemas/rag.py — same default, same reason.
DEFAULT_TOP_K = 5

# Sanity cap on the request payload itself — deliberately generous,
# and a different concern from chat_service.MAX_HISTORY_TURNS (which
# decides how much of this actually reaches the model). This just
# stops a malformed or runaway client from posting an unbounded body;
# the real "how much conversation memory" decision lives in the
# service layer, per this milestone's design goal of keeping prompt
# construction there.
MAX_HISTORY_TURNS_ACCEPTED = 50


class ChatHistoryTurn(BaseModel):
    """One prior turn of the conversation, as the frontend already holds it in state."""

    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("history content cannot be empty.")
        return stripped


class ChatRequest(BaseModel):
    """
    Body for POST /documents/{id}/chat. `history` is optional and
    defaults to empty, so existing callers that only ever sent
    `question` (and, before this milestone, nothing else) keep working
    unchanged — this is an additive field, not a breaking one, exactly
    as anticipated when this model was first written.

    Still no conversation_id: history is frontend-managed and resent
    with each request rather than looked up server-side by an id.
    Adding persisted, server-tracked conversations later is still just
    new fields on this same model (e.g. an optional conversation_id
    that, when present, means "load history server-side instead of
    trusting the body") — not a redesign of it.
    """

    question: str
    top_k: int = DEFAULT_TOP_K
    history: list[ChatHistoryTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS_ACCEPTED)

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

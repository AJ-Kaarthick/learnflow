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


# Sanity cap on how many documents one request can select — a UI
# multi-select is the expected caller (see routes_chat.py's docstring),
# and there's no realistic study session that needs more than this many
# documents in one conversation at once. Independent of
# MAX_HISTORY_TURNS_ACCEPTED above; this bounds documents, not turns.
MAX_DOCUMENT_IDS = 10


class MultiDocumentChatRequest(BaseModel):
    """
    Body for POST /documents/chat — the multi-document counterpart to
    ChatRequest. Same question/top_k/history shape (history is reused
    as-is via ChatHistoryTurn; conversation memory works the same way
    regardless of how many documents are selected), plus the set of
    documents to search across.
    """

    document_ids: list[str] = Field(min_length=1, max_length=MAX_DOCUMENT_IDS)
    question: str
    top_k: int = DEFAULT_TOP_K
    history: list[ChatHistoryTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS_ACCEPTED)

    @field_validator("document_ids")
    @classmethod
    def deduplicate_preserving_order(cls, value: list[str]) -> list[str]:
        # A multi-select UI shouldn't produce duplicates, but nothing
        # stops a client from sending the same id twice — deduping here
        # means chat_service never has to think about it.
        seen: set[str] = set()
        deduplicated = []
        for document_id in value:
            if document_id not in seen:
                seen.add(document_id)
                deduplicated.append(document_id)
        return deduplicated

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


class MultiDocumentSourceItem(SearchResultItem):
    """
    SearchResultItem plus which document a source came from — the
    "document information" a multi-document answer's sources need that
    a single-document one doesn't (the document is already implied by
    the URL for single-document chat/search).
    """

    document_id: str
    document_name: str


class MultiDocumentChatResponse(BaseModel):
    document_ids: list[str]
    question: str
    answer: str
    grounded: bool
    sources: list[MultiDocumentSourceItem]

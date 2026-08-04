from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.rag import SearchResultItem

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

    `top_k` defaults to `None`, which means "let retrieval decide" —
    see retrieval_service.compute_adaptive_top_k. Sending an explicit
    value always overrides that and is honored exactly, same as
    before this field became optional; the frontend already never
    sends `top_k` unless a caller explicitly asks for a specific
    number of sources, so this default change is invisible to it.
    """

    question: str
    top_k: int | None = None
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
    def positive(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
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

    `top_k` means "up to top_k chunks per selected document" (see
    retrieve_relevant_chunks), and, as of this milestone, defaults to
    `None` rather than a fixed number — see ChatRequest.top_k above
    for why; the same reasoning applies here.
    """

    document_ids: list[str] = Field(min_length=1, max_length=MAX_DOCUMENT_IDS)
    question: str
    top_k: int | None = None
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
    def positive(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
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


class DocumentSourceGroup(BaseModel):
    """
    All retrieved sources from one selected document, together — the
    grouped view of MultiDocumentChatResponse.sources (Milestone 3,
    requirement 7). Sources within a group are ordered strongest match
    first, same ordering convention as everywhere else sources appear.

    One of these exists per document actually requested in
    MultiDocumentChatRequest.document_ids, in that order, even when
    `sources` is empty for a document that contributed no evidence —
    an explicit "this document had nothing relevant" is exactly the
    clarity this grouping is meant to add over a flat, unordered list.
    """

    document_id: str
    document_name: str
    sources: list[SearchResultItem]


class MultiDocumentChatResponse(BaseModel):
    document_ids: list[str]
    question: str
    answer: str
    grounded: bool

    # Unchanged flat shape (document_id/document_name inline on each
    # item, same fields, same ordering behavior as before this
    # milestone) — existing callers that only ever read `sources` see
    # no difference.
    sources: list[MultiDocumentSourceItem]

    # Additive (Milestone 3, requirement 7): the same evidence as
    # `sources` above, regrouped by document so a caller doesn't have
    # to do that grouping itself to answer "what did document X
    # contribute." Never the only way to read the sources — `sources`
    # keeps working exactly as it always has for any caller that
    # hasn't been updated to use this.
    sources_by_document: list[DocumentSourceGroup]

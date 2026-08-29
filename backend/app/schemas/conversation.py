from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from app.schemas.rag import SearchResultItem

# Mirrors MAX_DOCUMENT_IDS in schemas/chat.py -- same "no realistic
# study session needs more than this many documents at once"
# reasoning, kept as its own constant here rather than imported, so
# this schema file stays self-contained -- matching how chat.py itself
# doesn't import from document.py either.
MAX_CONVERSATION_DOCUMENT_IDS = 10

MAX_TITLE_LENGTH = 200

# Mirrors MAX_HISTORY_TURNS_ACCEPTED in schemas/chat.py, applied to a
# single message's content instead of a history list -- a generous
# sanity cap on request body size, not the "how much conversation
# memory" decision (that's chat_service.MAX_HISTORY_TURNS, applied
# server-side to the persisted history this endpoint loads).
MAX_MESSAGE_CONTENT_LENGTH = 8000


def _assume_utc(value: object) -> object:
    """
    Restores the UTC-ness SQLite silently drops from every timestamp
    this backend writes -- see the "New conversation timestamp is
    wrong" fix (V2.4 Milestone 2 Phase 3 QA, issue 2).

    Every Conversation/Message timestamp is written server-side as
    `datetime.now(timezone.utc)` (see db/models.py), but SQLAlchemy's
    plain `DateTime` column (no `timezone=True` -- SQLite has no native
    timezone-aware type to back one) stores only the naive wall-clock
    digits, dropping `tzinfo` on write. Reading the row back therefore
    yields a *naive* `datetime` whose digits are UTC but whose
    `tzinfo` is None, and a naive `datetime` serializes with no offset
    suffix at all (e.g. "2026-08-27T14:33:00.123456" -- no "Z", no
    "+00:00").

    A browser doing `new Date(isoString)` on that offset-less string
    parses it as *local* time (the ECMAScript spec's rule for a
    date-time string with no zone), not UTC -- so a conversation
    created seconds ago showed as e.g. "5h ago" instead of "Just now"
    for anyone not in UTC+0: the same UTC digits got reinterpreted as
    the browser's own local time, then compared against the real
    current instant, off by exactly that timezone's UTC offset.

    Applied as a `mode="before"` field validator so it runs on the raw
    value straight out of the ORM object, before Pydantic's own
    datetime parsing/serialization -- an already-aware value (e.g.
    passed directly in a test, or once this project moves off SQLite)
    is left untouched.
    """
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _deduplicate_preserving_order(document_ids: list[str]) -> list[str]:
    """
    Shared by both request models below that accept a document_ids
    list -- same reasoning as MultiDocumentChatRequest's own
    deduplicate_preserving_order validator: a multi-select UI
    shouldn't produce duplicates, but nothing stops a client from
    sending the same id twice, so dedup here means the route never has
    to think about it.
    """
    seen: set[str] = set()
    deduplicated: list[str] = []
    for document_id in document_ids:
        if document_id not in seen:
            seen.add(document_id)
            deduplicated.append(document_id)
    return deduplicated


class ConversationDocumentSummary(BaseModel):
    """
    The trimmed document shape embedded in a conversation response --
    just enough for the frontend to render a document chip (name,
    readiness), not the full DocumentResponse (preview, character
    count, page count) nothing here needs.
    """

    id: str
    original_filename: str
    status: str

    model_config = {"from_attributes": True}


class MessageSourceItem(SearchResultItem):
    """
    SearchResultItem plus which document a source came from, mirroring
    MultiDocumentSourceItem in schemas/chat.py. Defined locally (not
    imported from chat.py) to keep this schema file self-contained,
    same as this file's other constants. document_id/document_name are
    optional since a source from a single-document conversation turn
    doesn't strictly need them (the document is already implied), but
    keeping the field present either way means callers don't need two
    different source shapes depending on conversation size.

    Nothing populates this yet as of Milestone 1 -- Message.sources_json
    is written starting Milestone 2.
    """

    document_id: str | None = None
    document_name: str | None = None


class MessageResponse(BaseModel):
    """
    One persisted turn, in the shape a future frontend needs to
    re-render a restored conversation. `sources` and `grounded` are
    null for user messages -- only an assistant message was ever
    "grounded" in anything.
    """

    id: str
    role: str
    content: str
    position: int
    created_at: datetime
    sources: list[MessageSourceItem] | None
    grounded: bool | None

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def _created_at_is_utc(cls, value: object) -> object:
        return _assume_utc(value)

    @staticmethod
    def from_message(message) -> "MessageResponse":
        sources = None
        if message.sources_json is not None:
            sources = [MessageSourceItem(**item) for item in message.sources_json]
        return MessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            position=message.position,
            created_at=message.created_at,
            sources=sources,
            grounded=message.grounded,
        )


class ConversationSummaryResponse(BaseModel):
    """
    What GET /conversations (the list/sidebar) and rename return --
    metadata only, no documents or messages, since listing every
    conversation shouldn't require loading each one's full history.
    Built directly via model_validate(conversation) since every field
    here is a plain column on Conversation, no separate query needed.
    """

    id: str
    title: str
    title_is_custom: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _timestamps_are_utc(cls, value: object) -> object:
        return _assume_utc(value)


class ConversationDetailResponse(ConversationSummaryResponse):
    """
    What creating, fetching, or updating a conversation's documents
    returns -- everything a future frontend needs to restore this
    conversation in one round trip: metadata, its currently associated
    documents, and its messages in position order.

    Unlike ConversationSummaryResponse, this can't be built with
    model_validate(conversation) alone -- documents and messages come
    from separate queries against ConversationDocument and Message
    (see routes_conversations.py), since no ORM relationship is
    configured between these tables (a deliberate choice, matching
    this project's existing no-relationships convention -- see
    Conversation's docstring in db/models.py).
    """

    documents: list[ConversationDocumentSummary]
    messages: list[MessageResponse]


class ConversationCreateRequest(BaseModel):
    """
    Body for POST /conversations. document_ids is optional and defaults
    to empty -- creating a conversation with no documents yet (e.g. an
    empty "New Conversation") is a normal, supported case, not an
    error; documents can always be attached afterward via
    PUT /conversations/{id}/documents.
    """

    document_ids: list[str] = Field(default_factory=list, max_length=MAX_CONVERSATION_DOCUMENT_IDS)

    @field_validator("document_ids")
    @classmethod
    def deduplicate_preserving_order(cls, value: list[str]) -> list[str]:
        return _deduplicate_preserving_order(value)


class ConversationDocumentsRequest(BaseModel):
    """
    Body for PUT /conversations/{id}/documents. Replaces the entire
    associated document set with exactly this list, including the
    empty list (a conversation can go back to having no documents).
    Chosen over separate add/remove endpoints because the frontend
    already computes the full desired set on every toggle (see the
    architecture review's frontend design), so one replace-the-set call
    maps onto that directly.
    """

    document_ids: list[str] = Field(default_factory=list, max_length=MAX_CONVERSATION_DOCUMENT_IDS)

    @field_validator("document_ids")
    @classmethod
    def deduplicate_preserving_order(cls, value: list[str]) -> list[str]:
        return _deduplicate_preserving_order(value)


class ConversationMessageRequest(BaseModel):
    """
    Body for POST /conversations/{id}/messages (Milestone 2). Deliberately
    thin compared to ChatRequest: no `history` field, since the whole
    point of a persistent conversation is that history is loaded
    server-side from the database (see routes_conversations.py) rather
    than resent by the client on every turn -- and no `document_ids`
    either, since the conversation's own ConversationDocument
    associations are what determine document scope now, not a
    per-request list.

    `top_k` is kept, mirroring ChatRequest.top_k exactly -- an explicit
    per-message override is still meaningful here (e.g. "give me more
    sources for this one answer"), and `None` still means "let
    retrieval decide" (see retrieval_service.compute_adaptive_top_k).
    """

    content: str = Field(max_length=MAX_MESSAGE_CONTENT_LENGTH)
    top_k: int | None = None

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content cannot be empty.")
        return stripped

    @field_validator("top_k")
    @classmethod
    def positive(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("top_k must be at least 1.")
        return value


class ConversationMessageResponse(BaseModel):
    """
    What POST /conversations/{id}/messages returns -- both messages
    this call persisted, in the same MessageResponse shape
    GET /conversations/{id} already uses for every other message, so a
    frontend never needs a second shape to render a turn depending on
    how it got there.

    Both are included, not just the assistant's reply: the user's
    message left the client with no id/position/created_at (those are
    assigned server-side on persist -- see send_message), so returning
    it here is what lets a frontend append the *actual persisted* turn
    to its view instead of re-deriving one from what it optimistically
    sent, or issuing a follow-up GET just to learn its id.
    """

    user_message: MessageResponse
    assistant_message: MessageResponse


class ConversationRenameRequest(BaseModel):
    """
    Body for PATCH /conversations/{id}. Setting a title here always
    marks it user-customized (see rename_conversation in
    routes_conversations.py) -- this is the only way title_is_custom
    ever becomes True, which is what permanently protects a manual
    rename from future AI auto-titling (Milestone 3).
    """

    title: str = Field(max_length=MAX_TITLE_LENGTH)

    @field_validator("title")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be empty.")
        return stripped

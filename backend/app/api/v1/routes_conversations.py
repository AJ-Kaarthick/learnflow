from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Conversation, ConversationDocument, Document, DocumentChunk, Message
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationDocumentSummary,
    ConversationDocumentsRequest,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationRenameRequest,
    ConversationSummaryResponse,
    MessageResponse,
)
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import answer_question

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation_or_404(conversation_id: str, db: Session) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


def _get_documents_or_404(document_ids: list[str], db: Session) -> list[Document]:
    """
    Loads every requested document, 404ing on the first id that
    doesn't resolve to a real Document -- same fail-fast, name-the-
    offender style as routes_chat.py's _get_indexed_document. Unlike
    that function, readiness/indexing is deliberately NOT checked
    here: associating a still-processing or unreadable document with a
    conversation is allowed, exactly like selecting one in the
    Document Library is allowed today. Whether a document is actually
    usable is a chat-send-time concern (Milestone 2), not an
    association-time one.
    """
    documents = []
    for document_id in document_ids:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}.")
        documents.append(document)
    return documents


def _document_summaries(conversation_id: str, db: Session) -> list[ConversationDocumentSummary]:
    """
    The documents currently associated with a conversation, ordered by
    when they were added (oldest first) so chip order stays stable
    rather than jumping around between requests. A document deleted
    after being associated has already had its ConversationDocument
    row cleaned up by delete_document (routes_documents.py), so it
    simply won't appear here -- callers never see a stale/dangling id.
    """
    rows = (
        db.query(ConversationDocument)
        .filter(ConversationDocument.conversation_id == conversation_id)
        .order_by(ConversationDocument.added_at.asc())
        .all()
    )
    if not rows:
        return []

    document_ids_in_order = [row.document_id for row in rows]
    documents_by_id = {
        document.id: document
        for document in db.query(Document).filter(Document.id.in_(document_ids_in_order)).all()
    }
    # Preserve `rows`' added_at order, not whatever order .in_() returns.
    return [
        ConversationDocumentSummary.model_validate(documents_by_id[document_id])
        for document_id in document_ids_in_order
        if document_id in documents_by_id
    ]


def _message_responses(conversation_id: str, db: Session) -> list[MessageResponse]:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.position.asc())
        .all()
    )
    return [MessageResponse.from_message(message) for message in messages]


def _to_detail_response(conversation: Conversation, db: Session) -> ConversationDetailResponse:
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        title_is_custom=conversation.title_is_custom,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        documents=_document_summaries(conversation.id, db),
        messages=_message_responses(conversation.id, db),
    )


def _get_indexed_document_for_conversation(document_id: str, db: Session) -> Document:
    """
    The exact same "exists, is ready, has readable text, is indexed"
    gate as routes_chat.py's _get_indexed_document, kept as its own
    copy here rather than imported -- matching this project's existing
    convention (see that function's own docstring, and
    docs/architecture.md's "Each route file owns its own request
    validation" rule) of every route file repeating this check rather
    than sharing one implementation across files.

    A conversation's associated documents are allowed to be
    unready/unindexed at association time (see _get_documents_or_404
    above) -- this is the chat-send-time check that actually enforces
    usability, run against every document a conversation is currently
    associated with, the same as routes_chat.py runs it against every
    document_id a direct multi-document chat request names explicitly.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} is not ready for chat (status: {document.status}).",
        )
    if not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                f"Document {document_id} has no readable text. LearnFlow needs "
                "extractable text to answer questions about it."
            ),
        )

    is_indexed = (
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).first()
        is not None
    )
    if not is_indexed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Document {document_id} has not been indexed yet. "
                "Call POST /documents/{id}/index first."
            ),
        )
    return document


def _get_conversation_documents_for_chat(conversation_id: str, db: Session) -> list[Document]:
    """
    Resolves a conversation's associated documents into the document
    scope a message send actually retrieves against -- the persisted-
    conversation counterpart to a MultiDocumentChatRequest.document_ids
    list, just sourced from ConversationDocument rows (see
    _document_summaries above, same ordering) instead of the request
    body, since the conversation's associations are what determine RAG
    document scope in this design (see the Milestone 2 architecture
    note on Message.sources_json in db/models.py).

    Requires at least one associated document, and every one of them
    to pass _get_indexed_document_for_conversation, exactly like
    POST /documents/chat requires every requested document_id to be
    ready and indexed -- a conversation with an unusable document set
    fails the whole send with a clear 400/404/422 naming the problem,
    the same as a direct multi-document chat call would, rather than
    silently answering from whichever documents happened to be usable.
    """
    rows = (
        db.query(ConversationDocument)
        .filter(ConversationDocument.conversation_id == conversation_id)
        .order_by(ConversationDocument.added_at.asc())
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=400,
            detail=(
                "This conversation has no associated documents. Associate at "
                "least one document (PUT /conversations/{id}/documents) before "
                "sending a message."
            ),
        )

    document_ids = [row.document_id for row in rows]
    return [_get_indexed_document_for_conversation(document_id, db) for document_id in document_ids]


def _load_history_turns(conversation_id: str, db: Session) -> list[dict[str, str]]:
    """
    The conversation's persisted messages, oldest first, converted to
    the same plain {"role", "content"} shape chat_service.answer_question
    already expects (see routes_chat.py's _history_to_plain_dicts,
    which does the identical conversion for the frontend-managed
    history ChatRequest carries). The database is this endpoint's
    source of truth for history -- see this file's module-level intent
    and the Milestone 2 goal in the architecture doc -- so this reads
    every persisted Message for the conversation rather than trusting
    anything the client sends.

    Deliberately returns the *full* persisted history, not just the
    last MAX_HISTORY_TURNS -- that trimming is answer_question's own
    job (chat_service.MAX_HISTORY_TURNS), and doing it twice here would
    be exactly the "duplicate or invent a second history
    implementation" this milestone was told not to do. At LearnFlow's
    scale (a single user's study conversations) loading a whole
    conversation's messages before trimming is the same accepted
    brute-force tradeoff retrieval_service.py already makes for chunk
    scoring, not a new one.
    """
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.position.asc())
        .all()
    )
    return [{"role": message.role, "content": message.content} for message in messages]


def _next_message_position(conversation_id: str, db: Session) -> int:
    """
    max(position) + 1 for this conversation, or 1 if it has no messages
    yet -- same "explicit, monotonically increasing integer, assigned
    by the caller" design as Message.position's own docstring
    describes. Computed once per send_message call and used for both
    the user and assistant message it creates (position, position + 1),
    so a conversation's turns stay strictly ordered even though both
    rows are created in the same request.
    """
    max_position = (
        db.query(func.max(Message.position))
        .filter(Message.conversation_id == conversation_id)
        .scalar()
    )
    return (max_position or 0) + 1


def _serialize_sources(chat_answer, documents_by_id: dict[str, Document]) -> list[dict] | None:
    """
    Snapshots chat_answer.chunks into the plain-dict shape
    Message.sources_json stores and MessageSourceItem later reads back
    (see schemas/conversation.py) -- the same "chunk id/index/content/
    score plus which document it came from" shape
    routes_chat.py._group_sources_by_document works with for
    MultiDocumentSourceItem, just written to a JSON column instead of
    returned directly, so a restored conversation keeps showing the
    exact sources an answer was grounded in even if that document is
    deleted later (see Message.sources_json's docstring in
    db/models.py).

    None -- not an empty list -- when there was no retrieved context at
    all to snapshot, matching that same docstring ("Null ... for
    assistant messages generated with no retrieved context at all").
    """
    if not chat_answer.chunks:
        return None
    return [
        {
            "chunk_id": scored.chunk.id,
            "chunk_index": scored.chunk.chunk_index,
            "content": scored.chunk.content,
            "score": scored.score,
            "document_id": scored.chunk.document_id,
            "document_name": documents_by_id[scored.chunk.document_id].original_filename,
        }
        for scored in chat_answer.chunks
    ]


def _set_conversation_documents(conversation_id: str, documents: list[Document], db: Session) -> None:
    """
    Replaces a conversation's entire associated document set: delete
    every existing ConversationDocument row for it, then insert one
    fresh row per document given. Simpler than diffing added/removed
    ids, at the accepted cost of resetting `added_at` for any document
    that was already associated and got re-sent -- see
    ConversationDocument's docstring in db/models.py.
    """
    db.query(ConversationDocument).filter(ConversationDocument.conversation_id == conversation_id).delete()
    for document in documents:
        db.add(ConversationDocument(conversation_id=conversation_id, document_id=document.id))


@router.post("", response_model=ConversationDetailResponse, status_code=201)
def create_conversation(
    payload: ConversationCreateRequest, db: Session = Depends(get_db)
) -> ConversationDetailResponse:
    """
    Creates a new, empty conversation -- optionally pre-associated with
    a set of documents in the same call, for the "click a document to
    start chatting" flow. Does not touch any AI provider: the title
    starts as the plain default ("New Conversation",
    title_is_custom=False) and stays that way until either the user
    renames it or Milestone 3's auto-titling generates one from the
    first message.
    """
    documents = _get_documents_or_404(payload.document_ids, db)

    conversation = Conversation()
    db.add(conversation)
    db.flush()  # assigns conversation.id without committing, so the association rows below can reference it

    for document in documents:
        db.add(ConversationDocument(conversation_id=conversation.id, document_id=document.id))

    db.commit()
    db.refresh(conversation)
    return _to_detail_response(conversation, db)


@router.get("", response_model=list[ConversationSummaryResponse])
def list_conversations(db: Session = Depends(get_db)) -> list[ConversationSummaryResponse]:
    """
    The conversation list/sidebar. Ordered by updated_at descending --
    most recently active first, the same convention as
    RECENTLY_OPENED for documents. Nothing in this milestone bumps
    updated_at after creation yet (see Conversation's docstring), so
    today this sorts by creation recency; it starts reflecting real
    activity as soon as Milestone 2 lands.
    """
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [ConversationSummaryResponse.model_validate(conversation) for conversation in conversations]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ConversationDetailResponse:
    """
    Full detail for restoring a conversation -- metadata, documents,
    and messages in one round trip, exactly what a future frontend
    needs when switching into a conversation or restoring one after a
    refresh.
    """
    conversation = _get_conversation_or_404(conversation_id, db)
    return _to_detail_response(conversation, db)


@router.patch("/{conversation_id}", response_model=ConversationSummaryResponse)
def rename_conversation(
    conversation_id: str, payload: ConversationRenameRequest, db: Session = Depends(get_db)
) -> ConversationSummaryResponse:
    """
    Manually renames a conversation. Always sets title_is_custom=True
    -- the one and only way that flag becomes True, and therefore the
    entire guarantee that a manual rename is never later overwritten
    by AI auto-titling (Milestone 3).
    """
    conversation = _get_conversation_or_404(conversation_id, db)
    conversation.title = payload.title
    conversation.title_is_custom = True
    db.commit()
    db.refresh(conversation)
    return ConversationSummaryResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)) -> None:
    """
    Deletes a conversation and everything that belongs only to it --
    its messages and its document associations. Documents themselves
    are never touched: this only removes the join rows pointing at
    them, exactly the same explicit-cleanup-in-the-route pattern
    delete_document (routes_documents.py) already uses for its own
    child tables, since no ORM relationship/cascade is configured here
    either.
    """
    _get_conversation_or_404(conversation_id, db)

    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.query(ConversationDocument).filter(ConversationDocument.conversation_id == conversation_id).delete()
    db.query(Conversation).filter(Conversation.id == conversation_id).delete()
    db.commit()


@router.put("/{conversation_id}/documents", response_model=ConversationDetailResponse)
def replace_conversation_documents(
    conversation_id: str, payload: ConversationDocumentsRequest, db: Session = Depends(get_db)
) -> ConversationDetailResponse:
    """
    Replaces a conversation's associated document set with exactly the
    given list -- adding, removing, or both, in one call. Critically,
    this never changes the conversation's id, title, or messages: it
    is the mechanism that lets documents change while the conversation
    identity (and everything a frontend keys off of) stays exactly the
    same, which is the entire point of Milestone 2 over the old
    document-set-derived conversation key.
    """
    conversation = _get_conversation_or_404(conversation_id, db)
    documents = _get_documents_or_404(payload.document_ids, db)

    _set_conversation_documents(conversation_id, documents, db)
    db.commit()
    db.refresh(conversation)
    return _to_detail_response(conversation, db)


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse, status_code=201)
async def send_message(
    conversation_id: str,
    payload: ConversationMessageRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> ConversationMessageResponse:
    """
    Sends one message in a persistent conversation (Milestone 2): loads
    the conversation's documents and persisted history, orchestrates
    the existing, unchanged chat_service.answer_question() over both,
    and persists the resulting user/assistant turn -- the wiring this
    whole milestone exists to add, deliberately without touching
    retrieval, prompt construction, or generation themselves.

    Nothing is written to the database until generation has actually
    succeeded: the user message and the assistant message are both
    added to the session and committed together, only after
    answer_question returns. An AIProviderError (the AI or embedding
    provider failing) is raised as a 502 before either message is
    added, so a failed turn leaves no trace at all -- no orphaned user
    question with no answer, and never a false "completed" assistant
    response (see this file's module docstring intent and the
    Data Integrity requirement it was written against). A caller that
    wants to retry after a 502 just posts the same message again.
    """
    conversation = _get_conversation_or_404(conversation_id, db)
    documents = _get_conversation_documents_for_chat(conversation_id, db)
    documents_by_id = {document.id: document for document in documents}

    history = _load_history_turns(conversation_id, db)

    try:
        result = await answer_question(
            documents=documents,
            question=payload.content,
            db=db,
            ai_provider=ai_provider,
            embedding_provider=embedding_provider,
            top_k=payload.top_k,
            history=history,
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    position = _next_message_position(conversation_id, db)
    sources_json = _serialize_sources(result, documents_by_id)

    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=payload.content,
        position=position,
    )
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=result.answer,
        position=position + 1,
        sources_json=sources_json,
        grounded=result.grounded,
    )
    db.add(user_message)
    db.add(assistant_message)

    # Bumps "most recently active" ordering for GET /conversations --
    # see Conversation.updated_at's docstring in db/models.py, which
    # names this exact call as the thing that would start updating it.
    conversation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ConversationMessageResponse(
        user_message=MessageResponse.from_message(user_message),
        assistant_message=MessageResponse.from_message(assistant_message),
    )

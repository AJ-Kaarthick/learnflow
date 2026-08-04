from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, DocumentChunk
from app.schemas.chat import (
    ChatHistoryTurn,
    ChatRequest,
    ChatResponse,
    DocumentSourceGroup,
    MultiDocumentChatRequest,
    MultiDocumentChatResponse,
    MultiDocumentSourceItem,
)
from app.schemas.rag import SearchResultItem
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import answer_question

router = APIRouter(prefix="/documents", tags=["chat"])


def _history_to_plain_dicts(history: list[ChatHistoryTurn]) -> list[dict[str, str]]:
    """
    Schema -> plain dict, at the API boundary, so the service layer
    (chat_service.answer_question) never depends on app.schemas — same
    reasoning as passing document_id / question as plain values rather
    than the whole request object. Shared by both routes below so the
    conversion logic exists in exactly one place.
    """
    return [{"role": turn.role, "content": turn.content} for turn in history]


def _group_sources_by_document(
    sources: list[MultiDocumentSourceItem],
    document_ids: list[str],
    documents_by_id: dict[str, Document],
) -> list[DocumentSourceGroup]:
    """
    Regroups a flat, score-ranked `sources` list into one
    DocumentSourceGroup per requested document (Milestone 3,
    requirement 7) — the same evidence `sources` already has, just
    organized the way the requirement describes ("Document A: chunk 2,
    chunk 6 / Document B: chunk 1, chunk 5") instead of interleaved by
    score.

    Iterates `document_ids` (the request's own order) rather than
    whatever order documents happen to appear in `sources`, so a
    document that contributed zero sources — because deduplication or
    a low relevance score left it unrepresented — still gets an empty
    group instead of silently disappearing from the response. That
    emptiness is itself useful information (see
    chat_service._build_informative_no_match_answer for the same idea
    applied to the answer text), not a case worth hiding.
    """
    sources_by_document_id: dict[str, list[SearchResultItem]] = {
        document_id: [] for document_id in document_ids
    }
    for source in sources:
        sources_by_document_id[source.document_id].append(
            SearchResultItem(
                chunk_id=source.chunk_id,
                chunk_index=source.chunk_index,
                content=source.content,
                score=source.score,
            )
        )

    return [
        DocumentSourceGroup(
            document_id=document_id,
            document_name=documents_by_id[document_id].original_filename,
            sources=sources_by_document_id[document_id],
        )
        for document_id in document_ids
    ]


def _get_indexed_document(document_id: str, db: Session) -> Document:
    """
    Shared by both routes below (single- and multi-document chat) —
    each selected document needs the exact same "exists, is ready, is
    indexed" check, so this exists once instead of being copy-pasted
    per document. Kept local to this file rather than shared with
    routes_rag.py, matching how routes_rag.py's own _get_ready_document
    isn't shared here either — each route file owns its own version of
    this lookup, which is the established convention (see
    routes_summary.py, routes_quiz.py, routes_flashcards.py,
    routes_mindmap.py, routes_rag.py — every one of them repeats this
    same check rather than importing a shared one).
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} is not ready for chat (status: {document.status}).",
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


@router.post("/{document_id}/chat", response_model=ChatResponse)
async def chat_with_document(
    document_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> ChatResponse:
    """
    Answers a question about one document, grounded only in its
    indexed chunks. Requires the document to already be indexed
    (POST /documents/{id}/index) — chat doesn't index on the caller's
    behalf, same reasoning as search in routes_rag.py: indexing costs
    one AI request per chunk and shouldn't happen as a side effect of
    an unrelated call.

    Single-document chat, unchanged in shape from before multi-document
    chat existed — it calls the exact same answer_question() as
    POST /documents/chat below, just with a one-document list.
    """
    document = _get_indexed_document(document_id, db)

    try:
        result = await answer_question(
            documents=[document],
            question=payload.question,
            db=db,
            ai_provider=ai_provider,
            embedding_provider=embedding_provider,
            top_k=payload.top_k,
            history=_history_to_plain_dicts(payload.history),
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return ChatResponse(
        document_id=document_id,
        question=payload.question,
        answer=result.answer,
        grounded=result.grounded,
        sources=[
            SearchResultItem(
                chunk_id=scored.chunk.id,
                chunk_index=scored.chunk.chunk_index,
                content=scored.chunk.content,
                score=scored.score,
            )
            for scored in result.chunks
        ],
    )


@router.post("/chat", response_model=MultiDocumentChatResponse)
async def chat_with_documents(
    payload: MultiDocumentChatRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> MultiDocumentChatResponse:
    """
    Answers a question grounded across several documents at once — the
    multi-document counterpart to POST /documents/{id}/chat above, for
    questions like "compare deadlocks in Operating Systems and DBMS"
    where the answer may draw on more than one selected document.

    Modeled as its own resource-level endpoint (/documents/chat, not
    nested under a single document id) rather than overloading the
    single-document route, since "chat across a set of documents" isn't
    naturally a sub-resource of any one of them. Both routes call the
    same answer_question() — this one just resolves multiple documents
    first and passes the list through; nothing about retrieval, prompt
    construction, or generation is duplicated between them.

    Every requested document must exist, be ready, and already be
    indexed, exactly like the single-document route — if any one of
    them isn't, the whole request fails with a 404/400 identifying
    which document, rather than silently answering from fewer documents
    than the user actually selected.
    """
    documents = [_get_indexed_document(document_id, db) for document_id in payload.document_ids]

    try:
        result = await answer_question(
            documents=documents,
            question=payload.question,
            db=db,
            ai_provider=ai_provider,
            embedding_provider=embedding_provider,
            top_k=payload.top_k,
            history=_history_to_plain_dicts(payload.history),
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    documents_by_id = {document.id: document for document in documents}

    sources = [
        MultiDocumentSourceItem(
            chunk_id=scored.chunk.id,
            chunk_index=scored.chunk.chunk_index,
            content=scored.chunk.content,
            score=scored.score,
            document_id=scored.chunk.document_id,
            document_name=documents_by_id[scored.chunk.document_id].original_filename,
        )
        for scored in result.chunks
    ]

    return MultiDocumentChatResponse(
        document_ids=payload.document_ids,
        question=payload.question,
        answer=result.answer,
        grounded=result.grounded,
        sources=sources,
        sources_by_document=_group_sources_by_document(sources, payload.document_ids, documents_by_id),
    )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, DocumentChunk
from app.schemas.rag import IndexResponse, SearchRequest, SearchResponse, SearchResultItem
from app.services.ai.base_provider import AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.rag.embedding_service import index_document
from app.services.rag.retrieval_service import retrieve_relevant_chunks

router = APIRouter(prefix="/documents", tags=["rag"])


def _get_ready_document(document_id: str, db: Session) -> Document:
    """
    Shared lookup for both routes below — same "exists, and is ready"
    check routes_summary.py and friends already do before generating
    anything for a document. Indexing and searching both need text
    that's actually been extracted, so both require status == "ready".
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for indexing (status: {document.status}).",
        )
    return document


@router.post("/{document_id}/index", response_model=IndexResponse, status_code=201)
async def create_index(
    document_id: str,
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> IndexResponse:
    """
    Chunks and embeds a document, so it becomes searchable. Idempotent,
    same as POST /summary: calling this again for an already-indexed
    document is a cheap no-op (status "already_indexed") rather than a
    re-embed, since index_document() only does the work once.

    This milestone exposes indexing as its own endpoint — rather than
    triggering it automatically at upload time, the way page_count is
    captured — because indexing costs one AI request per chunk and a
    document may never end up needing retrieval at all. Future
    features that build on this (chat, tutor mode) can call
    index_document() directly wherever makes sense for them: eagerly
    when a document is opened, lazily on a document's first question,
    or by hitting this endpoint first — retrieval_service.py doesn't
    care which.
    """
    document = _get_ready_document(document_id, db)

    already_indexed = (
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).first()
        is not None
    )

    try:
        chunks = await index_document(document, db, embedding_provider)
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return IndexResponse(
        document_id=document_id,
        chunk_count=len(chunks),
        status="already_indexed" if already_indexed else "indexed",
    )


@router.post("/{document_id}/search", response_model=SearchResponse)
async def search_document(
    document_id: str,
    payload: SearchRequest,
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    """
    Semantic search over one document's indexed chunks. This exists in
    this milestone to prove the retrieval foundation actually works
    end-to-end — see docs/architecture.md — not as the final "chat with
    PDF" feature. A future chat endpoint will most likely call
    retrieve_relevant_chunks() directly from its own route rather than
    making an HTTP call to this one, the same way routes_summary.py
    calls generate_summary_for_document() directly instead of calling
    another route.
    """
    _get_ready_document(document_id, db)

    is_indexed = (
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).first()
        is not None
    )
    if not is_indexed:
        raise HTTPException(
            status_code=400,
            detail="Document has not been indexed yet. Call POST /documents/{id}/index first.",
        )

    try:
        retrieval_result = await retrieve_relevant_chunks(
            document_ids=[document_id],
            query=payload.query,
            db=db,
            embedding_provider=embedding_provider,
            top_k=payload.top_k,
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return SearchResponse(
        document_id=document_id,
        query=payload.query,
        results=[
            SearchResultItem(
                chunk_id=result.chunk.id,
                chunk_index=result.chunk.chunk_index,
                content=result.chunk.content,
                score=result.score,
            )
            for result in retrieval_result.chunks
        ],
    )

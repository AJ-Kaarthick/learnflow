from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, DocumentChunk
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.rag import SearchResultItem
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import answer_question

router = APIRouter(prefix="/documents", tags=["chat"])


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
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for chat (status: {document.status}).",
        )

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
        result = await answer_question(
            document=document,
            question=payload.question,
            db=db,
            ai_provider=ai_provider,
            embedding_provider=embedding_provider,
            top_k=payload.top_k,
            # Schema -> plain dict here, at the API boundary, so the
            # service layer (chat_service.answer_question) never
            # depends on app.schemas — same reasoning as passing
            # document_id / question as plain values above rather than
            # the whole `payload` object.
            history=[{"role": turn.role, "content": turn.content} for turn in payload.history],
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

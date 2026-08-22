from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, Summary
from app.schemas.summary import SummaryResponse
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.summary_service import generate_summary_for_document

router = APIRouter(prefix="/documents", tags=["summary"])


def _get_ready_document(document_id: str, db: Session) -> Document:
    """
    Same "exists, is ready, and actually has readable text" check
    routes_rag.py's own _get_ready_document (and routes_chat.py's
    _get_indexed_document) already do before generating anything for a
    document — each route file owns its own version of this lookup
    rather than importing a shared one (see those functions'
    docstrings for the established convention).

    V2.4 Milestone 1 UX polish (issue 2) originally added the
    extracted_text check below to routes_rag.py and routes_chat.py
    only. Summary/Flashcards/Quiz/Mind Map generation went through
    this same "is document ready" shape but never got the matching
    extracted_text check, so a document whose extraction succeeded
    but found nothing (a scanned/image-only PDF, PPTX, or DOCX) would
    sail past this point and straight into build_summary_prompt() with
    an empty document, and the AI provider would return a plausible-
    looking summary of nothing — or, for Flashcards/Quiz/Mind Map,
    invent unrelated content to fill the shape it was asked for. This
    closes that gap the same way it was already closed for chat/search.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for summarization (status: {document.status}).",
        )
    if not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was detected in this document. LearnFlow "
                "needs extractable text to generate a summary for it."
            ),
        )
    return document


@router.post("/{document_id}/summary", response_model=SummaryResponse, status_code=201)
async def create_summary(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> SummaryResponse:
    document = _get_ready_document(document_id, db)

    try:
        summary = await generate_summary_for_document(document, db, provider)
    except AIProviderError as error:
        # 502 = "we're fine, the upstream AI service isn't" — distinct
        # from a 400 (bad request) or a 500 (bug in our code).
        raise HTTPException(status_code=502, detail=str(error))

    return SummaryResponse.model_validate(summary)


@router.get("/{document_id}/summary", response_model=SummaryResponse)
def get_summary(document_id: str, db: Session = Depends(get_db)) -> SummaryResponse:
    # Checked before the Summary lookup below so that a document whose
    # extracted_text has no readable content can never have a stale
    # Summary row (e.g. one generated before this guard existed, or
    # seeded directly) served back as if it were valid, real content
    # for this document. Only applies once the document is "ready" —
    # a document still processing or that failed simply has no summary
    # yet, which is the pre-existing 404 below, not this.
    document = db.query(Document).filter(Document.id == document_id).first()
    if (
        document is not None
        and document.status == "ready"
        and not (document.extracted_text or "").strip()
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was detected in this document. LearnFlow "
                "needs extractable text to generate a summary for it."
            ),
        )

    summary = db.query(Summary).filter(Summary.document_id == document_id).first()
    if summary is None:
        raise HTTPException(status_code=404, detail="No summary yet for this document.")
    return SummaryResponse.model_validate(summary)

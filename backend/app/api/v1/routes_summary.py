from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, Summary
from app.schemas.summary import SummaryResponse
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.summary_service import generate_summary_for_document

router = APIRouter(prefix="/documents", tags=["summary"])


@router.post("/{document_id}/summary", response_model=SummaryResponse, status_code=201)
async def create_summary(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> SummaryResponse:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for summarization (status: {document.status}).",
        )

    try:
        summary = await generate_summary_for_document(document, db, provider)
    except AIProviderError as error:
        # 502 = "we're fine, the upstream AI service isn't" — distinct
        # from a 400 (bad request) or a 500 (bug in our code).
        raise HTTPException(status_code=502, detail=str(error))

    return SummaryResponse.model_validate(summary)


@router.get("/{document_id}/summary", response_model=SummaryResponse)
def get_summary(document_id: str, db: Session = Depends(get_db)) -> SummaryResponse:
    summary = db.query(Summary).filter(Summary.document_id == document_id).first()
    if summary is None:
        raise HTTPException(status_code=404, detail="No summary yet for this document.")
    return SummaryResponse.model_validate(summary)

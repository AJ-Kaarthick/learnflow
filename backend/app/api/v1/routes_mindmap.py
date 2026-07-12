from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, MindMap
from app.schemas.mindmap import MindMapResponse
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.mindmap_service import generate_mindmap_for_document

router = APIRouter(prefix="/documents", tags=["mindmap"])


@router.post("/{document_id}/mindmap", response_model=MindMapResponse, status_code=201)
async def create_mindmap(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> MindMapResponse:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for mind map generation (status: {document.status}).",
        )

    try:
        mindmap = await generate_mindmap_for_document(document, db, provider)
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return MindMapResponse.model_validate(mindmap)


@router.get("/{document_id}/mindmap", response_model=MindMapResponse)
def get_mindmap(document_id: str, db: Session = Depends(get_db)) -> MindMapResponse:
    mindmap = db.query(MindMap).filter(MindMap.document_id == document_id).first()
    if mindmap is None:
        raise HTTPException(status_code=404, detail="No mind map yet for this document.")
    return MindMapResponse.model_validate(mindmap)

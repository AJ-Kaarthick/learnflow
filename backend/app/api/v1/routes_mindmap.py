from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, MindMap
from app.schemas.mindmap import MindMapResponse
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.mindmap_service import generate_mindmap_for_document

router = APIRouter(prefix="/documents", tags=["mindmap"])


def _get_ready_document(document_id: str, db: Session) -> Document:
    """
    Same "exists, is ready, and actually has readable text" check as
    routes_rag.py's _get_ready_document / routes_chat.py's
    _get_indexed_document / routes_summary.py's, routes_flashcards.py's
    and routes_quiz.py's own copies — see those docstrings for why
    this isn't a shared import. Without the extracted_text check, a
    document with nothing readable in it would reach
    build_mindmap_prompt() empty, and the AI would invent a generic
    structure with no real relationship to the document.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for mind map generation (status: {document.status}).",
        )
    if not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was detected in this document. LearnFlow "
                "needs extractable text to generate a mind map for it."
            ),
        )
    return document


@router.post("/{document_id}/mindmap", response_model=MindMapResponse, status_code=201)
async def create_mindmap(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> MindMapResponse:
    document = _get_ready_document(document_id, db)

    try:
        mindmap = await generate_mindmap_for_document(document, db, provider)
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return MindMapResponse.model_validate(mindmap)


@router.get("/{document_id}/mindmap", response_model=MindMapResponse)
def get_mindmap(document_id: str, db: Session = Depends(get_db)) -> MindMapResponse:
    # Checked before the MindMap lookup below for the same reason as
    # routes_summary.py's get_summary: a document with no readable
    # text must never have a stale/pre-existing mind map (generated
    # before this guard existed, or seeded directly) served back as if
    # it were valid content for this document.
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
                "needs extractable text to generate a mind map for it."
            ),
        )

    mindmap = db.query(MindMap).filter(MindMap.document_id == document_id).first()
    if mindmap is None:
        raise HTTPException(status_code=404, detail="No mind map yet for this document.")
    return MindMapResponse.model_validate(mindmap)

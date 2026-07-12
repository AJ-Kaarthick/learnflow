from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, Flashcard
from app.schemas.flashcard import FlashcardResponse
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.flashcard_service import generate_flashcards_for_document

router = APIRouter(prefix="/documents", tags=["flashcards"])


@router.post(
    "/{document_id}/flashcards", response_model=list[FlashcardResponse], status_code=201
)
async def create_flashcards(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> list[FlashcardResponse]:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for flashcard generation (status: {document.status}).",
        )

    try:
        flashcards = await generate_flashcards_for_document(document, db, provider)
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return [FlashcardResponse.model_validate(card) for card in flashcards]


@router.get("/{document_id}/flashcards", response_model=list[FlashcardResponse])
def get_flashcards(document_id: str, db: Session = Depends(get_db)) -> list[FlashcardResponse]:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    # A collection resource returns an empty list when there's nothing
    # yet, not a 404 — unlike the single-object Summary GET, "no
    # flashcards generated yet" is a normal, valid state, not an error.
    flashcards = (
        db.query(Flashcard)
        .filter(Flashcard.document_id == document_id)
        .order_by(Flashcard.position)
        .all()
    )
    return [FlashcardResponse.model_validate(card) for card in flashcards]

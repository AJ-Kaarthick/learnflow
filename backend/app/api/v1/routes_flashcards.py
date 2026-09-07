from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_identity
from app.db.database import get_db
from app.db.models import Document, Flashcard
from app.schemas.flashcard import FlashcardResponse
from app.schemas.identity import Identity
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.flashcard_service import generate_flashcards_for_document
from app.services.guest_limit_service import GuestLimitExceededError, GuestLimitType

router = APIRouter(prefix="/documents", tags=["flashcards"])


def _get_ready_document(document_id: str, db: Session, identity: Identity) -> Document:
    """
    Same "exists, is ready, and actually has readable text" check as
    routes_rag.py's _get_ready_document / routes_chat.py's
    _get_indexed_document / routes_summary.py's own copy — see those
    docstrings for why this isn't a shared import. Without the
    extracted_text check, a document with nothing readable in it (a
    scanned/image-only file) would reach build_flashcard_prompt() with
    an empty document and the AI would invent flashcards about
    whatever it wants instead of the document, since there's nothing
    document-specific in the prompt to ground it.

    V3 Milestone 1 Phase 3: also 404s for a document not owned by
    `identity` — see routes_summary.py's identical check for why.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None or not ownership_service.is_owned_by(document, identity):
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for flashcard generation (status: {document.status}).",
        )
    if not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was detected in this document. LearnFlow "
                "needs extractable text to generate flashcards for it."
            ),
        )
    return document


@router.post(
    "/{document_id}/flashcards", response_model=list[FlashcardResponse], status_code=201
)
async def create_flashcards(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    identity: Identity = Depends(get_current_identity),
) -> list[FlashcardResponse]:
    document = _get_ready_document(document_id, db, identity)

    # V3 Milestone 1 Phase 3: generation is cached (see
    # generate_flashcards_for_document's own docstring), so the guest
    # AI-generation limit is only checked/counted when there's nothing
    # cached yet — a re-fetch of an already-generated set is free.
    is_new_generation = (
        db.query(Flashcard).filter(Flashcard.document_id == document_id).first() is None
    )
    if is_new_generation:
        try:
            guest_limit_service.enforce_limit(db, identity, GuestLimitType.AI_GENERATION)
        except GuestLimitExceededError as error:
            raise guest_limit_service.to_http_exception(error)

    try:
        flashcards = await generate_flashcards_for_document(document, db, provider)
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    if is_new_generation:
        guest_limit_service.record_usage(db, identity, GuestLimitType.AI_GENERATION)

    return [FlashcardResponse.model_validate(card) for card in flashcards]


@router.get("/{document_id}/flashcards", response_model=list[FlashcardResponse])
def get_flashcards(
    document_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
) -> list[FlashcardResponse]:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None or not ownership_service.is_owned_by(document, identity):
        raise HTTPException(status_code=404, detail="Document not found.")

    # Checked before the Flashcard lookup below for the same reason as
    # routes_summary.py's get_summary: a document with no readable text
    # must never have a stale/pre-existing Flashcard set (generated
    # before this guard existed, or seeded directly) served back as if
    # it were valid content for this document.
    if document.status == "ready" and not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was detected in this document. LearnFlow "
                "needs extractable text to generate flashcards for it."
            ),
        )

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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_identity
from app.db.database import get_db
from app.db.models import Document, QuizQuestion
from app.schemas.identity import Identity
from app.schemas.quiz import QuizQuestionResponse
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_limit_service import GuestLimitExceededError, GuestLimitType
from app.services.quiz_service import generate_quiz_for_document

router = APIRouter(prefix="/documents", tags=["quiz"])


def _get_ready_document(document_id: str, db: Session, identity: Identity) -> Document:
    """
    Same "exists, is ready, and actually has readable text" check as
    routes_rag.py's _get_ready_document / routes_chat.py's
    _get_indexed_document / routes_summary.py's and
    routes_flashcards.py's own copies — see those docstrings for why
    this isn't a shared import. Without the extracted_text check, a
    document with nothing readable in it would reach build_quiz_prompt()
    empty, and the AI would invent quiz questions about whatever topic
    it wants — convincing-looking questions about content that was
    never actually in the document.

    V3 Milestone 1 Phase 3: also 404s for a document not owned by
    `identity` — see routes_summary.py's identical check for why.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None or not ownership_service.is_owned_by(document, identity):
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for quiz generation (status: {document.status}).",
        )
    if not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was detected in this document. LearnFlow "
                "needs extractable text to generate a quiz for it."
            ),
        )
    return document


@router.post("/{document_id}/quiz", response_model=list[QuizQuestionResponse], status_code=201)
async def create_quiz(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    identity: Identity = Depends(get_current_identity),
) -> list[QuizQuestionResponse]:
    document = _get_ready_document(document_id, db, identity)

    # V3 Milestone 1 Phase 3: generation is cached (see
    # generate_quiz_for_document's own docstring), so the guest
    # AI-generation limit is only checked/counted when there's nothing
    # cached yet — a re-fetch of an already-generated quiz is free.
    is_new_generation = (
        db.query(QuizQuestion).filter(QuizQuestion.document_id == document_id).first() is None
    )
    if is_new_generation:
        try:
            guest_limit_service.enforce_limit(db, identity, GuestLimitType.AI_GENERATION)
        except GuestLimitExceededError as error:
            raise guest_limit_service.to_http_exception(error)

    try:
        quiz_questions = await generate_quiz_for_document(document, db, provider)
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    if is_new_generation:
        guest_limit_service.record_usage(db, identity, GuestLimitType.AI_GENERATION)

    return [QuizQuestionResponse.model_validate(question) for question in quiz_questions]


@router.get("/{document_id}/quiz", response_model=list[QuizQuestionResponse])
def get_quiz(
    document_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
) -> list[QuizQuestionResponse]:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None or not ownership_service.is_owned_by(document, identity):
        raise HTTPException(status_code=404, detail="Document not found.")

    # Checked before the QuizQuestion lookup below for the same reason
    # as routes_summary.py's get_summary: a document with no readable
    # text must never have a stale/pre-existing quiz (generated before
    # this guard existed, or seeded directly) served back as if it
    # were valid content for this document.
    if document.status == "ready" and not (document.extracted_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text was detected in this document. LearnFlow "
                "needs extractable text to generate a quiz for it."
            ),
        )

    quiz_questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.document_id == document_id)
        .order_by(QuizQuestion.position)
        .all()
    )
    return [QuizQuestionResponse.model_validate(question) for question in quiz_questions]

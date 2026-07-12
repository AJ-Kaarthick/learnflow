from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, QuizQuestion
from app.schemas.quiz import QuizQuestionResponse
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.quiz_service import generate_quiz_for_document

router = APIRouter(prefix="/documents", tags=["quiz"])


@router.post("/{document_id}/quiz", response_model=list[QuizQuestionResponse], status_code=201)
async def create_quiz(
    document_id: str,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> list[QuizQuestionResponse]:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for quiz generation (status: {document.status}).",
        )

    try:
        quiz_questions = await generate_quiz_for_document(document, db, provider)
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return [QuizQuestionResponse.model_validate(question) for question in quiz_questions]


@router.get("/{document_id}/quiz", response_model=list[QuizQuestionResponse])
def get_quiz(document_id: str, db: Session = Depends(get_db)) -> list[QuizQuestionResponse]:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    quiz_questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.document_id == document_id)
        .order_by(QuizQuestion.position)
        .all()
    )
    return [QuizQuestionResponse.model_validate(question) for question in quiz_questions]

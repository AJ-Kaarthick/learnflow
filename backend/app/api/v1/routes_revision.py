from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_identity
from app.db.database import get_db
from app.db.models import Document, RevisionSession
from app.schemas.identity import Identity
from app.schemas.revision import (
    RevisionQuestionResponse,
    RevisionSessionCreateRequest,
    RevisionSessionDetailResponse,
    RevisionSessionDocumentSummary,
    RevisionSessionSummaryResponse,
)
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_limit_service import GuestLimitExceededError, GuestLimitType
from app.services.revision_service import generate_revision_session

router = APIRouter(prefix="/revision", tags=["revision"])


def _resolve_revision_documents(
    document_ids: list[str],
    db: Session,
    identity: Identity,
) -> list[Document]:
    """
    Validates existence, ownership, and readability of the requested documents.

    - Every document must exist and be accessible to the requesting identity (404 if not).
    - For single-document selections:
        - Must be 'ready' (400 if uploading, processing, or failed).
        - Must have non-blank extracted text (422 if empty/whitespace-only).
    - For multi-document selections:
        - Filters documents to only those ready with readable text.
        - If zero documents are readable, rejects with 400.
    """
    documents: list[Document] = []
    for doc_id in document_ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None or not ownership_service.is_owned_by(doc, identity):
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}.")
        documents.append(doc)

    if len(documents) == 1:
        doc = documents[0]
        if doc.status != "ready":
            raise HTTPException(
                status_code=400,
                detail=f"Document is not ready for revision (status: {doc.status}).",
            )
        if not (doc.extracted_text or "").strip():
            raise HTTPException(
                status_code=422,
                detail=(
                    "No readable text was detected in this document. LearnFlow "
                    "needs extractable text to generate revision questions."
                ),
            )
        return [doc]

    contributing: list[Document] = []
    for doc in documents:
        if doc.status == "ready" and (doc.extracted_text or "").strip():
            contributing.append(doc)

    if not contributing:
        raise HTTPException(
            status_code=400,
            detail=(
                "No readable documents available for revision. "
                "Please select at least one ready document with readable text."
            ),
        )

    return contributing


def _serialize_session_detail(session: RevisionSession) -> RevisionSessionDetailResponse:
    """
    Transforms a persistent RevisionSession and its relations into a RevisionSessionDetailResponse.
    Gracefully handles archived or deleted documents and questions.
    """
    doc_summaries: list[RevisionSessionDocumentSummary] = []
    doc_ids: list[str] = []
    for rsd in session.documents:
        doc_ids.append(rsd.document_id)
        doc_summaries.append(
            RevisionSessionDocumentSummary(
                document_id=rsd.document_id,
                original_filename=rsd.document.original_filename if rsd.document else "Archived Document",
                status=rsd.document.status if rsd.document else "archived",
                added_at=rsd.added_at,
            )
        )

    question_responses: list[RevisionQuestionResponse] = []
    for q in session.questions:
        doc_title = q.source_document.original_filename if q.source_document else None
        question_responses.append(
            RevisionQuestionResponse(
                id=q.id,
                session_id=q.session_id,
                position=q.position,
                question_type=q.question_type,
                question_text=q.question_text,
                options=q.options,
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                source_document_id=q.source_document_id,
                source_document_title=doc_title,
                source_chunk_id=q.source_chunk_id,
                evidence_snippet=q.evidence_snippet,
                evidence_metadata=q.evidence_metadata,
                created_at=q.created_at,
            )
        )

    return RevisionSessionDetailResponse(
        id=session.id,
        title=session.title,
        owner_type=session.owner_type,
        owner_id=session.owner_id,
        status=session.status,
        config=session.config,
        total_questions=session.total_questions,
        score=session.score,
        created_at=session.created_at,
        completed_at=session.completed_at,
        document_ids=doc_ids,
        documents=doc_summaries,
        questions=question_responses,
    )


@router.post("/sessions", response_model=RevisionSessionDetailResponse, status_code=201)
async def create_revision_session(
    payload: RevisionSessionCreateRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    identity: Identity = Depends(get_current_identity),
) -> RevisionSessionDetailResponse:
    """
    Creates a new RevisionSession across 1 to 10 selected documents.
    Generates grounded questions using AI, persists session and question entities,
    and enforces guest usage quotas.
    """
    # 1. Validate document ownership and readiness
    contributing = _resolve_revision_documents(payload.document_ids, db, identity)

    # 2. Enforce guest AI quota
    try:
        guest_limit_service.enforce_limit(db, identity, GuestLimitType.AI_GENERATION)
    except GuestLimitExceededError as error:
        raise guest_limit_service.to_http_exception(error)

    # 3. Generate questions and persist atomically
    try:
        session = await generate_revision_session(
            db=db,
            identity=identity,
            documents=contributing,
            payload=payload,
            ai_provider=ai_provider,
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    # 4. Record guest usage only after successful generation and persistence
    guest_limit_service.record_usage(db, identity, GuestLimitType.AI_GENERATION)

    return _serialize_session_detail(session)


@router.get("/sessions", response_model=list[RevisionSessionSummaryResponse])
def list_revision_sessions(
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
) -> list[RevisionSessionSummaryResponse]:
    """
    Lists revision sessions belonging to the calling identity, newest first.
    """
    query = db.query(RevisionSession)
    query = ownership_service.scope_to_owner(query, RevisionSession, identity)
    sessions = query.order_by(RevisionSession.created_at.desc()).all()

    results: list[RevisionSessionSummaryResponse] = []
    for s in sessions:
        doc_ids = [rsd.document_id for rsd in s.documents]
        results.append(
            RevisionSessionSummaryResponse(
                id=s.id,
                title=s.title,
                owner_type=s.owner_type,
                owner_id=s.owner_id,
                status=s.status,
                config=s.config,
                total_questions=s.total_questions,
                score=s.score,
                created_at=s.created_at,
                completed_at=s.completed_at,
                document_ids=doc_ids,
            )
        )
    return results


@router.get("/sessions/{session_id}", response_model=RevisionSessionDetailResponse)
def get_revision_session(
    session_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
) -> RevisionSessionDetailResponse:
    """
    Retrieves full details of a specific revision session, including its bound documents
    and generated questions. 404s if not found or not owned by the calling identity.
    """
    session = db.query(RevisionSession).filter(RevisionSession.id == session_id).first()
    if session is None or not ownership_service.is_owned_by(session, identity):
        raise HTTPException(status_code=404, detail="Revision session not found.")

    return _serialize_session_detail(session)

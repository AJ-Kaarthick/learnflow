from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_identity
from app.db.database import get_db
from app.db.models import Document, RevisionQuestion, RevisionSession
from app.schemas.identity import Identity
from app.schemas.revision import (
    RevisionAttemptResponse,
    RevisionAttemptSubmitRequest,
    RevisionQuestionResponse,
    RevisionSessionCreateRequest,
    RevisionSessionDetailResponse,
    RevisionSessionDocumentSummary,
    RevisionSessionSummaryResponse,
)
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider
from app.services.evaluation_service import (
    complete_revision_session,
    evaluate_mcq_answer,
    evaluate_open_ended_answer,
    record_question_attempt,
)
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
        attempt_responses = [
            RevisionAttemptResponse(
                id=att.id,
                question_id=att.question_id,
                session_id=att.session_id,
                attempt_number=att.attempt_number,
                submitted_answer=att.submitted_answer,
                is_correct=att.is_correct,
                score=att.score,
                feedback=att.feedback,
                explanation=q.explanation,
                correct_answer=q.correct_answer,
                evaluation_metadata=att.evaluation_metadata,
                created_at=att.created_at,
            )
            for att in (q.attempts or [])
        ]
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
                attempts=attempt_responses,
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


@router.post(
    "/sessions/{session_id}/questions/{question_id}/attempts",
    response_model=RevisionAttemptResponse,
    status_code=201,
)
async def submit_question_attempt(
    session_id: str,
    question_id: str,
    payload: RevisionAttemptSubmitRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    identity: Identity = Depends(get_current_identity),
) -> RevisionAttemptResponse:
    """
    Submits a learner answer for a question in a revision session.
    Evaluates deterministically for MCQs or via AI for open-ended questions.
    Persists a new RevisionAttempt with sequential attempt_number and updates session history.
    """
    # 1. Validate session existence and ownership
    session = db.query(RevisionSession).filter(RevisionSession.id == session_id).first()
    if session is None or not ownership_service.is_owned_by(session, identity):
        raise HTTPException(status_code=404, detail="Revision session not found.")

    # 2. Validate question belongs to this session
    question = db.query(RevisionQuestion).filter(RevisionQuestion.id == question_id).first()
    if question is None or question.session_id != session.id:
        raise HTTPException(status_code=404, detail="Question not found in this revision session.")

    # 3. Reject submissions on completed sessions
    if session.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot submit attempts to an already completed revision session.",
        )

    # 4. Evaluation and quota branching
    submitted_text = (payload.submitted_answer or "").strip()

    if question.question_type == "multiple_choice":
        # Deterministic MCQ evaluation (NO AI provider invocation, NO guest quota consumed)
        is_correct, score, feedback, metadata = evaluate_mcq_answer(
            question=question,
            submitted_answer=payload.submitted_answer,
        )
        consumed_quota = False
    else:
        # Open-ended question evaluation
        if not submitted_text:
            # Deterministic evaluation for empty submissions (NO AI call, NO quota consumed)
            is_correct, score, feedback, metadata = (
                False,
                0.0,
                "No answer was provided. Please write an explanation or response to receive feedback.",
                {"evaluation_type": "deterministic_empty", "reasoning": "Empty submission"},
            )
            consumed_quota = False
        else:
            # Enforce guest quota before invoking AI
            try:
                guest_limit_service.enforce_limit(db, identity, GuestLimitType.AI_GENERATION)
            except GuestLimitExceededError as error:
                raise guest_limit_service.to_http_exception(error)

            try:
                is_correct, score, feedback, metadata = await evaluate_open_ended_answer(
                    question=question,
                    submitted_answer=payload.submitted_answer,
                    ai_provider=ai_provider,
                )
            except AIProviderError as error:
                raise HTTPException(status_code=502, detail=str(error))

            consumed_quota = True

    # 5. Persist attempt atomically
    attempt = record_question_attempt(
        db=db,
        session=session,
        question=question,
        submitted_answer=payload.submitted_answer,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        evaluation_metadata=metadata,
    )

    # 6. Record guest quota only after successful AI evaluation and persistence
    if consumed_quota:
        guest_limit_service.record_usage(db, identity, GuestLimitType.AI_GENERATION)

    return RevisionAttemptResponse(
        id=attempt.id,
        question_id=attempt.question_id,
        session_id=attempt.session_id,
        attempt_number=attempt.attempt_number,
        submitted_answer=attempt.submitted_answer,
        is_correct=attempt.is_correct,
        score=attempt.score,
        feedback=attempt.feedback,
        explanation=question.explanation,
        correct_answer=question.correct_answer,
        evaluation_metadata=attempt.evaluation_metadata,
        created_at=attempt.created_at,
    )


@router.post("/sessions/{session_id}/complete", response_model=RevisionSessionDetailResponse)
def complete_session(
    session_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
) -> RevisionSessionDetailResponse:
    """
    Finalizes an in-progress revision session, computes the cumulative session score
    from the latest attempts on each question, and transitions status to 'completed'.
    """
    session = db.query(RevisionSession).filter(RevisionSession.id == session_id).first()
    if session is None or not ownership_service.is_owned_by(session, identity):
        raise HTTPException(status_code=404, detail="Revision session not found.")

    if session.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot complete a revision session that is already completed.",
        )

    try:
        updated_session = complete_revision_session(session, db)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return _serialize_session_detail(updated_session)

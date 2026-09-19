from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_identity
from app.db.database import get_db
from app.db.models import Document
from app.schemas.identity import Identity
from app.schemas.learn import LearnOutlineRequest, LearnOutlineResponse, LearnTopicRequest, LearnTopicResponse
from app.services import guest_limit_service, ownership_service
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.guest_limit_service import GuestLimitExceededError, GuestLimitType
from app.services.learn_service import generate_learn_outline, generate_learn_topic

router = APIRouter(prefix="/study/learn", tags=["learn"])


def _resolve_learn_documents(
    document_ids: list[str],
    db: Session,
    identity: Identity,
) -> tuple[list[Document], list[tuple[Document, str]]]:
    """
    Validates ownership and readiness across the requested document IDs.

    - Every document must exist and be accessible to the requesting identity (404 if not).
    - For single-document selections:
        - Must be 'ready' (400 if processing, uploading, or failed).
        - Must have non-blank extracted text (422 if empty/whitespace-only).
    - For multi-document selections:
        - Filters documents into contributing (ready + readable) and excluded (unready/empty).
        - If zero documents are readable, rejects with 400.
    """
    documents: list[Document] = []
    for doc_id in document_ids:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if document is None or not ownership_service.is_owned_by(document, identity):
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}.")
        documents.append(document)

    if len(documents) == 1:
        doc = documents[0]
        if doc.status != "ready":
            raise HTTPException(
                status_code=400,
                detail=f"Document is not ready for study (status: {doc.status}).",
            )
        if not (doc.extracted_text or "").strip():
            raise HTTPException(
                status_code=422,
                detail="No readable text was detected in this document. LearnFlow needs extractable text to generate study material.",
            )
        return [doc], []

    contributing: list[Document] = []
    excluded: list[tuple[Document, str]] = []

    for doc in documents:
        if doc.status != "ready":
            excluded.append((doc, f"status_{doc.status}"))
        elif not (doc.extracted_text or "").strip():
            excluded.append((doc, "no_readable_text"))
        else:
            contributing.append(doc)

    if not contributing:
        raise HTTPException(
            status_code=400,
            detail="No readable documents available for study. Please select at least one ready document with readable text.",
        )

    return contributing, excluded


@router.post("/outline", response_model=LearnOutlineResponse)
async def create_learn_outline(
    payload: LearnOutlineRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    identity: Identity = Depends(get_current_identity),
) -> LearnOutlineResponse:
    """
    Generates a structured curriculum / study outline across 1 to 10 selected documents.
    Enforces server-side document ownership, document readiness, and guest AI quotas.
    """
    contributing, excluded = _resolve_learn_documents(payload.document_ids, db, identity)

    try:
        guest_limit_service.enforce_limit(db, identity, GuestLimitType.AI_GENERATION)
    except GuestLimitExceededError as error:
        raise guest_limit_service.to_http_exception(error)

    try:
        response = await generate_learn_outline(
            requested_document_ids=payload.document_ids,
            contributing_documents=contributing,
            excluded_documents=excluded,
            ai_provider=ai_provider,
            depth=payload.depth,
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    guest_limit_service.record_usage(db, identity, GuestLimitType.AI_GENERATION)
    return response


@router.post("/topic", response_model=LearnTopicResponse)
async def create_learn_topic(
    payload: LearnTopicRequest,
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    identity: Identity = Depends(get_current_identity),
) -> LearnTopicResponse:
    """
    Generates a RAG-grounded topic deep-dive explanation with source citations,
    key terms, key takeaways, and optional contextual actions (simplify, elaborate, example).
    """
    contributing, _ = _resolve_learn_documents(payload.document_ids, db, identity)

    try:
        guest_limit_service.enforce_limit(db, identity, GuestLimitType.AI_GENERATION)
    except GuestLimitExceededError as error:
        raise guest_limit_service.to_http_exception(error)

    try:
        response = await generate_learn_topic(
            requested_document_ids=payload.document_ids,
            readable_documents=contributing,
            topic_id=payload.topic_id,
            topic_title=payload.topic_title,
            db=db,
            ai_provider=ai_provider,
            embedding_provider=embedding_provider,
            action=payload.action,
            depth=payload.depth,
            parent_topic_title=payload.parent_topic_title,
            context=payload.context,
        )
    except AIProviderError as error:
        raise HTTPException(status_code=502, detail=str(error))

    guest_limit_service.record_usage(db, identity, GuestLimitType.AI_GENERATION)
    return response
